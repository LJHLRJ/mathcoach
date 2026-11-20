"""Streamlit 单页装配：只渲染 session 层给的视图，不写判定逻辑。"""
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from mathcoach.config import content_strict
from mathcoach.content.loader import ContentError, load_content
from mathcoach.domain.models import Consent, Exercise, ExerciseKind, Phase
from mathcoach.export.package import (
    build_export_artifact,
    describe_export,
    write_export,
)
from mathcoach.llm import OfflineProvider, build_provider
from mathcoach.memory.dashboard import build_dashboard
from mathcoach.memory.path import build_learning_path
from mathcoach.memory.report import build_weekly_report
from mathcoach.memory.repository import build_repository, load_consent
from mathcoach.memory.review_package import (
    REVIEW_PACKAGE_LIMIT_S,
    build_review_package,
)
from mathcoach.memory.scheduler import build_plan
from mathcoach.safety.guards import REFUSAL_TEXT, Blocked
from mathcoach.safety.redlines import (
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
)
from mathcoach.session.challenge import (
    build_challenge_state,
    save_challenge_result,
)
from mathcoach.session.daily import (
    DailyState,
    build_daily_questions,
    current_question,
    elapsed_seconds,
    finish_daily,
    record_daily_mistake,
    remaining_seconds,
    save_daily_result,
    submit_daily_answer,
    time_is_up,
)
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = Path(__file__).parent / "content"
MODE_SESSION = "陪练"
MODE_DASHBOARD = "仪表盘"
MODE_DAILY = "每日挑战"
MODE_CHALLENGE = "挑战赛"
MODE_PATH = "学习路径"
MODE_WEEKLY = "周报"
MODE_REVIEW = "智能复习包"
MODE_VARIANTS = "错题变式"
MODE_EXPORT = "导出学习包"
MODES = (
    MODE_SESSION,
    MODE_DASHBOARD,
    MODE_DAILY,
    MODE_CHALLENGE,
    MODE_PATH,
    MODE_WEEKLY,
    MODE_REVIEW,
    MODE_VARIANTS,
    MODE_EXPORT,
)

st.set_page_config(page_title="数学陪练", page_icon="📘")


@st.cache_resource
def _load_cards():
    try:
        cards, result = load_content(CONTENT_ROOT, strict=content_strict())
    except ContentError as exc:
        st.error(f"内容加载失败：\n{exc}")
        st.stop()
    for warning in result.warnings:
        st.warning(f"{warning.location}: {warning.message}")
    return cards


cards = _load_cards()

if "provider" not in st.session_state:
    st.session_state.provider = build_provider()
if "consent" not in st.session_state:
    st.session_state.consent = load_consent()
if "repository" not in st.session_state:
    st.session_state.repository = build_repository(st.session_state.consent)
if "engine" not in st.session_state:
    st.session_state.engine = SessionEngine(
        card=cards[0],
        provider=st.session_state.provider,
        repository=st.session_state.repository,
        consent=st.session_state.consent,
    )

provider = st.session_state.provider
engine: SessionEngine = st.session_state.engine


def _render_mistake_book(repository) -> None:
    with st.expander("错题本", expanded=False):
        entries = repository.list_mistakes(limit=10)
        if not entries:
            st.caption("还没有错题。")
            return
        for entry in entries:
            st.markdown(f"**{entry.stem}**")
            st.caption(
                f"你的答案：{entry.user_answer} · 正确答案：{entry.correct_answer} · "
                f"{entry.error_type.value} · {entry.review_state.value}"
            )


def _render_review_plan(repository) -> None:
    with st.expander("复习清单", expanded=False):
        items = repository.list_review_items()
        if not items:
            st.caption("暂无待复习内容。")
            return
        plan = build_plan(items, datetime.now(timezone.utc))
        for label, group in (
            ("今天", plan.today),
            ("明天", plan.tomorrow),
            ("三天后", plan.in_three_days),
        ):
            if not group:
                continue
            st.markdown(f"**{label}**")
            for item in group:
                st.markdown(f"- {item.mistake.stem}（{item.mistake.error_type.value}）")


STAGE_LABELS = {"highschool": "高中", "undergraduate": "本科", "graduate": "研究生"}


def _render_card_selector() -> None:
    labels = {
        card.id: f"{STAGE_LABELS[card.stage.value]} · {card.course} · {card.name}"
        for card in cards
    }
    card_ids = [card.id for card in cards]
    current_id = st.session_state.engine.card.id
    index = card_ids.index(current_id) if current_id in card_ids else 0
    selected = st.selectbox(
        "选择卡片",
        card_ids,
        index=index,
        format_func=lambda card_id: labels[card_id],
        key="card_selector",
    )
    if selected != current_id:
        selected_card = next(card for card in cards if card.id == selected)
        st.session_state.engine = SessionEngine(
            card=selected_card,
            provider=st.session_state.provider,
            repository=st.session_state.repository,
            consent=st.session_state.consent,
        )
        st.rerun()


def _render_answer_input(exercise: Exercise, key_suffix: str | None = None) -> str:
    suffix = key_suffix or f"{exercise.id}_{len(engine.state.attempts)}"
    if exercise.kind in (ExerciseKind.CHOICE, ExerciseKind.FIND_ERROR):
        if not exercise.options:
            return st.text_input("输入答案", key=f"text_{suffix}")
        return st.radio("选择答案", exercise.options, key=f"choice_{suffix}")
    if exercise.kind is ExerciseKind.TRUEFALSE:
        return st.radio("判断", ["对", "错"], key=f"bool_{suffix}")
    if exercise.kind is ExerciseKind.MULTI:
        selected = st.multiselect(
            "选择所有正确选项", exercise.options, key=f"multi_{suffix}"
        )
        return ",".join(selected)
    labels = {
        ExerciseKind.FILL: "输入答案",
        ExerciseKind.EXPR: "输入表达式（如 x**2 + 1）",
        ExerciseKind.PROOF_ORDER: "输入步骤顺序（用逗号分隔，如 1,2,3）",
        ExerciseKind.MATCH: "输入配对（如 A=1;B=2）",
    }
    return st.text_input(labels.get(exercise.kind, "输入答案"), key=f"text_{suffix}")


def _render_sidebar() -> None:
    consent: Consent = st.session_state.consent
    repository = st.session_state.repository
    with st.sidebar:
        st.header("学习设置")
        _render_card_selector()
        st.selectbox("功能", MODES, key="app_mode")
        memory = st.toggle(
            "保存学习收据（本机）", value=consent.memory, key="consent_memory"
        )
        mistake_book = st.toggle(
            "记录错题本（本机）", value=consent.mistake_book, key="consent_book"
        )
        new_consent = Consent(memory=memory, mistake_book=mistake_book)
        if new_consent != consent:
            repository.save_consent(new_consent)
            repository.record_audit("consent", "ok")
            new_repository = build_repository(new_consent)
            new_repository.save_consent(new_consent)
            repository.close()
            st.session_state.consent = new_consent
            st.session_state.repository = new_repository
            engine.repository = new_repository
            engine.consent = new_consent
            st.rerun()

        if not (consent.memory or consent.mistake_book):
            st.info("游客模式：本次学习数据只存在内存中。")
        st.divider()
        if consent.mistake_book:
            _render_mistake_book(repository)
            _render_review_plan(repository)
        else:
            st.caption("错题本已关闭。")


def _render_hint_actions() -> None:
    with st.expander("需要提示？"):
        if st.button("给步骤（最高 L4）", key="hint_step"):
            engine.request_hint("step")
            st.rerun()
        if st.button("直接给答案（最高 L4）", key="hint_answer"):
            engine.request_hint("answer")
            st.rerun()
        if st.button("开放 L5（需先尝试 L1—L4）", key="hint_level5"):
            engine.request_hint("level5")
            st.rerun()


def _render_session() -> None:
    view = engine.view
    st.caption(f"当前卡片：{engine.card.name} · {engine.card.course}")
    st.subheader(view.title)
    st.write(view.body)
    if view.notice:
        st.info(view.notice)

    if view.phase is Phase.GOAL_CONFIRM:
        goal = st.text_input("今天想练到什么？", key="goal_input")
        if st.button("确认目标", key="confirm_goal"):
            try:
                engine.confirm_goal(goal)
            except Blocked:
                st.error(REFUSAL_TEXT)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()

    elif view.phase is Phase.EXPLAIN:
        if st.button("开始小测", key="begin_quiz"):
            engine.begin_quiz()
            st.rerun()

    elif view.phase is Phase.QUIZ:
        answer = _render_answer_input(engine.current_exercise)
        if st.button("提交答案", key="submit_answer"):
            engine.submit_answer(answer)
            st.rerun()
        _render_hint_actions()

    elif view.phase is Phase.DIAGNOSE:
        selected = st.radio(
            "选择更贴近的错因",
            view.options,
            key=f"diagnosis_{engine.state.exercise_id}_{len(engine.state.attempts)}",
        )
        if st.button("确认错因", key="confirm_diagnosis"):
            engine.confirm_diagnosis(selected)
            st.rerun()

    elif view.phase is Phase.HINT:
        if st.button("再试一次", key="retry"):
            engine.retry()
            st.rerun()
        _render_hint_actions()

    elif view.phase is Phase.RECEIPT:
        if st.button("继续", key="advance"):
            engine.advance()
            st.rerun()

    elif view.phase is Phase.WRAPUP:
        if st.button("重新开始", key="restart"):
            st.session_state.engine = SessionEngine(
                card=engine.card,
                provider=provider,
                repository=st.session_state.repository,
                consent=st.session_state.consent,
            )
            st.rerun()


def _render_dashboard() -> None:
    summary = build_dashboard(
        st.session_state.repository, datetime.now(timezone.utc)
    )
    st.subheader("学习仪表盘")
    columns = st.columns(4)
    columns[0].metric("收据总数", summary.receipts)
    columns[1].metric("独立完成", summary.independent)
    columns[2].metric("错题总数", summary.mistakes)
    columns[3].metric("今天待复习", summary.due_today)
    st.caption(
        f"半独立完成 {summary.semi_independent} 次 · "
        f"平均最高提示层级 L{summary.average_hint_level:.1f}"
    )
    st.markdown(
        f"复习状态：未复习 {summary.unreviewed} · "
        f"复习中 {summary.reviewing} · 已掌握 {summary.mastered}"
    )
    if summary.top_errors:
        st.markdown(
            "**高频错因**："
            + " · ".join(f"{name} {count}" for name, count in summary.top_errors)
        )
    if summary.top_courses:
        st.markdown(
            "**高频课程**："
            + " · ".join(f"{name} {count}" for name, count in summary.top_courses)
        )
    if summary.receipts == 0 and summary.mistakes == 0:
        st.info("还没有学习记录，先完成一次讲解 → 小测闭环。")


def _render_quiz_summary(state: DailyState, now: datetime, title: str) -> None:
    used = min(state.time_limit_s, elapsed_seconds(state, now))
    st.success(
        f"{title}：{state.correct}/{len(state.questions)} 正确，用时 {used} 秒。"
    )
    if state.timed_out:
        st.caption("时间到，未作答题目不计分。")
    if state.feedback:
        st.info(state.feedback)


def _render_active_quiz(
    state: DailyState,
    *,
    key_prefix: str,
    on_submission=None,
    on_finish=None,
    summary_title: str = "挑战结束",
) -> None:
    now = datetime.now(timezone.utc)
    if not state.finished and time_is_up(state, now):
        finish_daily(state, now, timed_out=True)
    if state.finished:
        if not state.persisted and on_finish is not None:
            on_finish(state, now)
            state.persisted = True
        _render_quiz_summary(state, now, summary_title)
        return

    st.caption(
        f"剩余 {remaining_seconds(state, now)} 秒 · "
        f"第 {state.index + 1}/{len(state.questions)} 题"
    )
    if state.feedback:
        st.info(state.feedback)
    question = current_question(state)
    if question is None:
        return
    st.markdown(f"**{question.card.course} · {question.card.name}**")
    st.write(question.exercise.stem)
    answer = _render_answer_input(
        question.exercise, key_suffix=f"{key_prefix}_{state.index}"
    )
    if st.button("提交答案", key=f"{key_prefix}_submit"):
        submission = submit_daily_answer(state, answer, now)
        if submission is not None and on_submission is not None:
            on_submission(submission, answer, now)
        if state.finished and on_finish is not None and not state.persisted:
            on_finish(state, now)
            state.persisted = True
        st.rerun()


def _render_daily_challenge() -> None:
    now = datetime.now(timezone.utc)
    day_key = now.date().isoformat()
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    st.subheader("每日挑战 · 5 分钟")

    state: DailyState | None = st.session_state.get("daily_state")
    if state is not None and state.date_key != day_key:
        st.session_state.pop("daily_state", None)
        state = None

    result = repository.get_daily_result(day_key)
    if state is None and result is not None:
        st.success(
            f"今天的挑战已完成：{result.correct}/{result.total} 正确，"
            f"用时 {result.duration_s} 秒。"
        )
        st.caption("明天再来。")
        return

    if state is None:
        st.write("5 道跨模块小题，限时 5 分钟。答错会自动进入错题本。")
        if st.button("开始 5 分钟挑战", key="start_daily"):
            st.session_state.daily_state = DailyState(
                date_key=day_key,
                questions=build_daily_questions(cards, now.date()),
                started_at=now,
            )
            st.rerun()
        return

    def _on_submission(submission, answer, moment) -> None:
        if submission.correct is False:
            record_daily_mistake(
                repository, consent, submission.question, answer, moment
            )

    def _on_finish(finished_state, moment) -> None:
        save_daily_result(repository, consent, finished_state, moment)

    _render_active_quiz(
        state,
        key_prefix=f"daily_{day_key}",
        on_submission=_on_submission,
        on_finish=_on_finish,
    )


def _render_challenge() -> None:
    now = datetime.now(timezone.utc)
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    st.subheader("挑战赛 · 10 题 5 分钟")

    best = repository.list_challenge_results(limit=5)
    if best:
        st.markdown("**本地最好成绩**")
        for rank, result in enumerate(best, start=1):
            st.markdown(
                f"{rank}. {result.score}/{result.total} · {result.duration_s} 秒"
            )

    state: DailyState | None = st.session_state.get("challenge_state")
    if state is None:
        st.write("10 道跨模块小题，限时 5 分钟，可反复挑战。")
        if st.button("开始挑战赛", key="start_challenge"):
            st.session_state.challenge_state = build_challenge_state(
                cards, now, time.time_ns()
            )
            st.rerun()
        return

    def _on_submission(submission, answer, moment) -> None:
        if submission.correct is False:
            record_daily_mistake(
                repository, consent, submission.question, answer, moment
            )

    def _on_finish(finished_state, moment) -> None:
        save_challenge_result(repository, consent, finished_state, moment)

    _render_active_quiz(
        state,
        key_prefix="challenge",
        on_submission=_on_submission,
        on_finish=_on_finish,
        summary_title="挑战赛结束",
    )
    if state.finished and st.button("再来一局", key="restart_challenge"):
        st.session_state.pop("challenge_state", None)
        st.rerun()


def _render_learning_path() -> None:
    repository = st.session_state.repository
    path = build_learning_path(
        cards,
        repository.list_receipts(limit=None),
        repository.list_mistakes(limit=None),
    )
    st.subheader("学习路径")
    if path.recommended_card is not None:
        card = path.recommended_card
        st.success(
            f"建议下一张：{STAGE_LABELS[card.stage.value]} · {card.course} · "
            f"{card.name}（{path.recommended_reason}）"
        )
    else:
        st.success(path.recommended_reason)

    for course in path.courses:
        label = (
            f"{STAGE_LABELS[course.stage.value]} · {course.course}"
            f"（{course.completed_cards}/{course.total_cards}）"
        )
        with st.expander(label, expanded=False):
            ratio = (
                course.completed_cards / course.total_cards
                if course.total_cards
                else 0.0
            )
            st.progress(ratio)
            for item in course.cards:
                st.caption(
                    f"{item.card.name} · {item.status} · "
                    f"{item.completed_exercises}/{item.total_exercises}"
                )


def _render_weekly_report() -> None:
    report = build_weekly_report(
        st.session_state.repository, datetime.now(timezone.utc)
    )
    st.subheader("学习周报 · 最近 7 天")
    st.caption(f"{report.start} ~ {report.end}")

    columns = st.columns(4)
    columns[0].metric("收据", report.receipts)
    columns[1].metric("独立完成", report.independent)
    columns[2].metric("新增错题", report.mistakes)
    columns[3].metric("今天待复习", report.due_today)
    st.caption(f"平均最高提示层级 L{report.average_hint_level:.1f}")

    st.markdown("**每日收据**")
    for day, count in report.daily_receipts:
        st.markdown(f"- {day}：{count}")

    if report.top_errors:
        st.markdown(
            "**本周高频错因**："
            + " · ".join(f"{name} {count}" for name, count in report.top_errors)
        )
    st.markdown(f"**错因趋势（文字版）**：{report.trend.summary}")
    if report.trend.last_week:
        st.caption(
            "上周："
            + " · ".join(
                f"{name} {count}" for name, count in report.trend.last_week
            )
        )


def _record_review_write(exercise_id: str, independent: bool) -> None:
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    now = datetime.now(timezone.utc)
    try:
        assert_write_allowed("review", consent=consent)
    except (WriteBlocked, ConfirmationRequired) as exc:
        repository.record_audit("review", f"blocked:{exc.reason}")
        st.warning("写操作被安全规则拦截。")
        return
    repository.record_review(exercise_id, independent=independent, now=now)
    repository.record_audit("review", "ok")


def _render_review_package() -> None:
    now = datetime.now(timezone.utc)
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    st.subheader("智能复习包 · 15 分钟 5 题")
    if not consent.mistake_book:
        st.info("错题本已关闭，无法生成复习包。")
        return

    state: DailyState | None = st.session_state.get("review_state")
    if state is None:
        package = build_review_package(repository, cards, now)
        if not package.questions:
            st.info(package.reason)
            return
        st.write(package.reason)
        if st.button("开始复习包", key="start_review"):
            st.session_state.review_state = DailyState(
                date_key=f"review-{time.time_ns()}",
                questions=package.questions,
                started_at=now,
                time_limit_s=REVIEW_PACKAGE_LIMIT_S,
            )
            st.rerun()
        return

    def _on_submission(submission, answer, moment) -> None:
        if submission.correct is True:
            _record_review_write(submission.question.exercise.id, True)
        elif submission.correct is False:
            _record_review_write(submission.question.exercise.id, False)
            record_daily_mistake(
                repository, consent, submission.question, answer, moment
            )

    _render_active_quiz(
        state,
        key_prefix="review",
        on_submission=_on_submission,
        summary_title="复习包完成",
    )
    if state.finished and st.button("再来一组", key="restart_review"):
        st.session_state.pop("review_state", None)
        st.rerun()


def _mistake_variants(entry, exercises_by_id: dict) -> list[str]:
    variants = entry.exercise_snapshot.get("variants") or []
    if variants:
        return list(variants)
    exercise = exercises_by_id.get(entry.exercise_id)
    return list(exercise.variants) if exercise else []


def _render_variant_practice() -> None:
    st.subheader("错题变式")
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    if not consent.mistake_book:
        st.info("错题本已关闭，无法练习变式。")
        return

    exercises_by_id = {
        exercise.id: exercise for card in cards for exercise in card.exercises
    }
    mistakes = [
        mistake
        for mistake in repository.list_mistakes(limit=None, include_mastered=False)
        if _mistake_variants(mistake, exercises_by_id)
    ]
    if not mistakes:
        st.info("还没有带变式的错题。先在陪练或每日挑战中答错一题。")
        return

    labels = {
        mistake.id: f"{mistake.stem}（{mistake.error_type.value}）"
        for mistake in mistakes
    }
    selected_id = st.selectbox(
        "选择错题",
        list(labels),
        format_func=lambda mistake_id: labels[mistake_id],
        key="variant_select",
    )
    entry = next(mistake for mistake in mistakes if mistake.id == selected_id)
    st.markdown(f"**原题**：{entry.stem}")
    for variant in _mistake_variants(entry, exercises_by_id):
        st.markdown(f"- **变式**：{variant}")
    with st.expander("查看思路"):
        st.write(entry.exercise_snapshot.get("solution_outline", "暂无"))

    left, right = st.columns(2)
    if left.button("我已独立完成", key="variant_done"):
        _record_review_write(entry.exercise_id, True)
        st.rerun()
    if right.button("仍需复习", key="variant_retry"):
        _record_review_write(entry.exercise_id, False)
        st.rerun()


def _render_export() -> None:
    st.subheader("导出学习包")
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    if not (consent.memory or consent.mistake_book):
        st.info("游客模式不可导出，请先开启本机记忆或错题本。")
        return

    default_dir = str(Path.home() / "mathcoach-exports")
    directory = st.text_input("导出目录", value=default_dir, key="export_dir")
    now = datetime.now(timezone.utc)
    artifact = build_export_artifact(repository, cards, Path(directory), now)

    st.markdown(f"**导出摘要**：{artifact.summary_text()}")
    st.code(describe_export(artifact), language="text")
    for name in artifact.files:
        st.markdown(f"- {name}")
    with st.expander("预览 learning_package.md"):
        st.code(artifact.files["learning_package.md"][:3000], language="markdown")
    st.caption("只含学习字段，不含聊天原文或身份信息；导出目录不能在仓库内。")

    confirmation = st.text_input(
        "确认语句（我确认执行此操作）", key="export_confirmation"
    )
    if st.button("确认导出", key="confirm_export"):
        try:
            written = write_export(
                artifact,
                consent=consent,
                confirmation=confirmation,
                repository=repository,
            )
        except ConfirmationRequired:
            st.error("导出未执行：请输入完整确认语句“我确认执行此操作”。")
        except WriteBlocked as exc:
            st.error(f"导出未执行：{exc.reason}")
        else:
            st.success(f"已导出 {len(written)} 个文件到 {directory}")


_render_sidebar()

st.title("数学陪练")
if isinstance(provider, OfflineProvider) or getattr(provider, "degraded", False):
    st.caption("离线模板模式：讲解使用确定性模板，判分逻辑不变。")

mode = st.session_state.get("app_mode", MODE_SESSION)
if mode == MODE_DASHBOARD:
    _render_dashboard()
elif mode == MODE_DAILY:
    _render_daily_challenge()
elif mode == MODE_CHALLENGE:
    _render_challenge()
elif mode == MODE_PATH:
    _render_learning_path()
elif mode == MODE_WEEKLY:
    _render_weekly_report()
elif mode == MODE_REVIEW:
    _render_review_package()
elif mode == MODE_VARIANTS:
    _render_variant_practice()
elif mode == MODE_EXPORT:
    _render_export()
else:
    _render_session()
