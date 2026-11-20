"""Streamlit 单页装配：只渲染 session 层给的视图，不写判定逻辑。"""
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from mathcoach.config import content_strict
from mathcoach.content.loader import ContentError, load_content
from mathcoach.domain.models import Consent, Exercise, ExerciseKind, Phase
from mathcoach.llm import OfflineProvider, build_provider
from mathcoach.memory.dashboard import build_dashboard
from mathcoach.memory.repository import build_repository, load_consent
from mathcoach.memory.scheduler import build_plan
from mathcoach.safety.guards import REFUSAL_TEXT, Blocked
from mathcoach.safety.redlines import (
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
)
from mathcoach.session.daily import (
    DAILY_TIME_LIMIT_S,
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
MODE_VARIANTS = "错题变式"
MODES = (MODE_SESSION, MODE_DASHBOARD, MODE_DAILY, MODE_VARIANTS)

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


def _render_daily_summary(state: DailyState, now: datetime) -> None:
    used = min(DAILY_TIME_LIMIT_S, elapsed_seconds(state, now))
    st.success(
        f"挑战结束：{state.correct}/{len(state.questions)} 正确，用时 {used} 秒。"
    )
    if state.timed_out:
        st.caption("时间到，未作答题目不计分。")
    if state.feedback:
        st.info(state.feedback)


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

    if not state.finished and time_is_up(state, now):
        finish_daily(state, now, timed_out=True)
        save_daily_result(repository, consent, state, now)

    if state.finished:
        _render_daily_summary(state, now)
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
        question.exercise, key_suffix=f"daily_{day_key}_{state.index}"
    )
    if st.button("提交答案", key="submit_daily"):
        submission = submit_daily_answer(state, answer, now)
        if submission is not None and submission.correct is False:
            record_daily_mistake(repository, consent, submission.question, answer, now)
        if state.finished:
            save_daily_result(repository, consent, state, now)
        st.rerun()


def _record_variant_review(exercise_id: str, independent: bool) -> None:
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
        _record_variant_review(entry.exercise_id, True)
        st.rerun()
    if right.button("仍需复习", key="variant_retry"):
        _record_variant_review(entry.exercise_id, False)
        st.rerun()


_render_sidebar()

st.title("数学陪练")
if isinstance(provider, OfflineProvider) or getattr(provider, "degraded", False):
    st.caption("离线模板模式：讲解使用确定性模板，判分逻辑不变。")

mode = st.session_state.get("app_mode", MODE_SESSION)
if mode == MODE_DASHBOARD:
    _render_dashboard()
elif mode == MODE_DAILY:
    _render_daily_challenge()
elif mode == MODE_VARIANTS:
    _render_variant_practice()
else:
    _render_session()
