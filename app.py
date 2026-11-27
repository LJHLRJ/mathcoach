"""Streamlit 单页装配：只渲染 session 层给的视图，不写判定逻辑。"""
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

import mathcoach
from mathcoach.config import content_strict, resolve_content_root
from mathcoach.content.loader import (
    ContentError,
    load_content,
    load_narrative,
    load_prerequisites,
)
from mathcoach.content.validator import ValidationError, validate_prerequisites
from mathcoach.domain.basis import basis_for_mastery
from mathcoach.domain.bkt import initial_mastery
from mathcoach.domain.explanation import (
    ErrorLocalization,
    PrerequisiteRef,
    build_explanation,
    locate_error,
)
from mathcoach.domain.grade_index import (
    GradeIndex,
    GradeIndexError,
    load_grade_index,
    load_grade_spans,
)
from mathcoach.domain.knowledge_tree import (
    KnowledgeTree,
    KnowledgeTreeError,
    load_knowledge_tree,
)
from mathcoach.domain.learning_path import Recommendation, recommend
from mathcoach.domain.models import (
    Consent,
    ErrorType,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    MistakeEntry,
    Phase,
    Receipt,
    ReviewState,
)
from mathcoach.domain.narrative import (
    NarrativeProgress,
    build_progress,
    next_node,
)
from mathcoach.domain.prerequisites import Gap, MistakeStat, trace_gap
from mathcoach.domain.receipt import RESTATEMENT_SPARSE
from mathcoach.domain.spaced_repetition import quality_from_independence
from mathcoach.export.package import (
    build_export_artifact,
    describe_export,
    write_export,
)
from mathcoach.llm import OfflineProvider, build_provider
from mathcoach.memory.dashboard import build_dashboard
from mathcoach.memory.path import build_learning_path
from mathcoach.memory.report import build_mistake_stats, build_weekly_report
from mathcoach.memory.repository import Repository, build_repository
from mathcoach.memory.review_package import (
    REVIEW_PACKAGE_LIMIT_S,
    build_review_package,
)
from mathcoach.memory.scheduler import ReviewPlan, build_plan
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
    DailySubmission,
    build_daily_questions,
    build_similar_questions,
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
from mathcoach.timeutil import end_of_local_day, local_day, local_day_key
from mathcoach.ui.components import (
    PRIMARY,
    SKELETON_CARD,
    SKELETON_PANEL,
    button_kwargs,
    loading_skeleton,
)
from mathcoach.ui.first_run import (
    FirstRunError,
    initialize_consent,
    initialize_repository,
    initialize_settings,
)
from mathcoach.ui.grade_page import (
    load_default_grade,
    render_grade_page,
)
from mathcoach.ui.icons import (
    ICON_BOOK,
    ICON_CHECK,
    ICON_ERROR,
    ICON_EXPORT,
    ICON_HINT,
    ICON_INFO,
    ICON_PLAY,
    ICON_RESTART,
    ICON_REVIEW,
    ICON_SUBMIT,
    ICON_UPDATE,
)
from mathcoach.ui.knowledge_browser import (
    learning_status_for,
    load_learning_cards_enabled,
    render_knowledge_browser,
    render_learning_status,
)
from mathcoach.ui.layout import card, hint_block, kpi_row, math_markdown
from mathcoach.ui.milestones import (
    celebrate_five_correct,
    celebrate_review_complete,
)
from mathcoach.ui.motion import (
    inject_micro_interactions,
    play_pending_celebration,
    render_dynamic_background,
)
from mathcoach.ui.onboarding import (
    mark_first_use_done,
    render_onboarding,
    repository_has_history,
)
from mathcoach.ui.settings import (
    apply_runtime_settings,
    current_settings,
    inject_font_size_css,
    render_settings_page,
)
from mathcoach.ui.sound import play_pending_feedback, queue_feedback
from mathcoach.ui.theme import inject_theme
from mathcoach.ui.visuals.registry import render_visual
from mathcoach.update_check import UpdateCheckError, check_for_update

CONTENT_ROOT = resolve_content_root(Path(__file__))
MODE_SESSION = "陪练"
MODE_GRADE = "按年级"
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
    MODE_GRADE,
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
def _load_cards() -> list[KnowledgeCard]:
    """加载知识点卡并校验先修关系；失败时中止页面。"""
    try:
        cards, result = load_content(CONTENT_ROOT, strict=content_strict())
        # 先修关系是启动硬校验：ID 必须存在且无环
        validate_prerequisites(
            load_prerequisites(CONTENT_ROOT), [card.id for card in cards]
        )
    except (ContentError, ValidationError) as exc:
        st.error(f"{ICON_ERROR} 内容加载失败：\n{exc}")
        st.stop()
    for warning in result.warnings:
        st.warning(f"{warning.location}: {warning.message}")
    return cards


@st.cache_resource
def _load_knowledge_tree() -> KnowledgeTree | None:
    """知识点树是只读展示数据；加载失败时回退到卡片字段。"""
    try:
        return load_knowledge_tree(CONTENT_ROOT / "knowledge_tree.yaml")
    except KnowledgeTreeError as exc:
        st.warning(f"{ICON_INFO} 知识点树暂不可用：{exc}")
        return None


@st.cache_resource
def _load_grade_index() -> GradeIndex | None:
    """加载年级元数据；失败时提示并返回 None。"""
    try:
        return load_grade_index(CONTENT_ROOT)
    except GradeIndexError as exc:
        st.error(f"{ICON_ERROR} 年级元数据加载失败：{exc}")
        return None


@st.cache_resource
def _load_grade_spans() -> dict[str, tuple[str, ...]] | None:
    """加载知识点年级范围；失败时提示并返回 None。"""
    try:
        return load_grade_spans(CONTENT_ROOT / "knowledge_tree.yaml")
    except GradeIndexError as exc:
        st.warning(f"{ICON_INFO} 知识点年级范围暂不可用：{exc}")
        return None


with st.spinner("正在准备讲解…"):
    cards = _load_cards()
try:
    prerequisites = load_prerequisites(CONTENT_ROOT)
    narrative_nodes = load_narrative(CONTENT_ROOT)
except ContentError as exc:
    st.error(f"{ICON_ERROR} 内容加载失败：\n{exc}")
    st.stop()


def _gaps_from_stats(
    stats: dict[str, MistakeStat],
    entries: list[MistakeEntry],
    card_id: str | None = None,
) -> list[Gap]:
    """用已取好的统计与错题列表计算先修缺口。"""
    if card_id is not None:
        entries = [entry for entry in entries if entry.card_id == card_id]
    gaps: list[Gap] = []
    seen: set[tuple[str, ...]] = set()
    for entry in entries:
        for gap in trace_gap(entry.card_id, prerequisites, stats):
            if gap.chain not in seen:
                seen.add(gap.chain)
                gaps.append(gap)
    return gaps


def _collect_gaps(
    repository: Repository, card_id: str | None = None
) -> list[Gap]:
    """汇总未掌握错题的先修缺口；同一链路只保留一次。"""
    stats = build_mistake_stats(repository.list_mistakes(limit=None))
    entries = repository.list_mistakes(limit=None, include_mastered=False)
    return _gaps_from_stats(stats, entries, card_id)


def _render_gap_diagnosis(gaps: list[Gap]) -> None:
    """先修诊断：结论在前，依据用 caption 紧跟其后。"""
    if not gaps:
        return
    st.markdown("**先修诊断**")
    for gap in gaps:
        chain = " → ".join(gap.chain)
        st.markdown(
            f"- 当前卡点：{chain}\n"
            f"  原因：{gap.reason}\n"
            f"  建议先复习：{gap.chain[-1]}"
        )
        if gap.basis:
            st.caption(f"依据：{gap.basis}")


try:
    if "consent" not in st.session_state:
        st.session_state.consent = initialize_consent()
    if "settings" not in st.session_state:
        st.session_state.settings = initialize_settings(
            st.session_state.consent
        )
    apply_runtime_settings(st.session_state.settings)
    if "provider" not in st.session_state:
        st.session_state.provider = build_provider()
    if "repository" not in st.session_state:
        st.session_state.repository = initialize_repository(
            st.session_state.consent
        )
    if "engine" not in st.session_state:
        st.session_state.engine = SessionEngine(
            card=cards[0],
            provider=st.session_state.provider,
            repository=st.session_state.repository,
            consent=st.session_state.consent,
        )
except FirstRunError as exc:
    st.error(f"{ICON_ERROR} {exc}")
    st.stop()

provider = st.session_state.provider
engine: SessionEngine = st.session_state.engine
if "onboarding_had_history" not in st.session_state:
    st.session_state["onboarding_had_history"] = repository_has_history(
        st.session_state.repository
    )
inject_theme(st.session_state.consent)
inject_font_size_css(st.session_state.settings.font_size)


def _render_mistake_book(repository: Repository) -> None:
    """渲染最近错题与逐题先修诊断。"""
    entries = repository.list_mistakes(limit=10)
    if not entries:
        st.caption("还没有错题。")
        return
    stats = build_mistake_stats(repository.list_mistakes(limit=None))
    active_mistakes = repository.list_mistakes(
        limit=None, include_mastered=False
    )
    for entry in entries:
        st.markdown(f"**{entry.stem}**")
        st.caption(
            f"你的答案：{entry.user_answer} · 正确答案：{entry.correct_answer} · "
            f"{entry.error_type.value} · {entry.review_state.value}"
        )
        gaps = _gaps_from_stats(stats, active_mistakes, entry.card_id)
        if gaps:
            _render_gap_diagnosis(gaps)


def _render_review_plan(repository: Repository) -> None:
    """按今日上限渲染复习清单。"""
    items = repository.list_review_items()
    if not items:
        st.caption("暂无待复习内容。")
        return
    st.markdown("**复习清单**")
    now = datetime.now(timezone.utc)
    limit = current_settings(st.session_state.consent).daily_review_limit
    plan = build_plan(items, now, limit=len(items) if limit == 0 else limit)
    if limit > 0:
        today = plan.today[:limit]
        remaining = max(limit - len(today), 0)
        tomorrow = plan.tomorrow[:remaining]
        remaining = max(remaining - len(tomorrow), 0)
        in_three_days = plan.in_three_days[:remaining]
        plan = ReviewPlan(
            today=today,
            tomorrow=tomorrow,
            in_three_days=in_three_days,
        )
    kpi_row(
        [
            ("今天", str(len(plan.today))),
            ("明天", str(len(plan.tomorrow))),
            ("三天后", str(len(plan.in_three_days))),
        ]
    )
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
    """渲染卡片下拉框；切换后重建引擎并重跑。"""
    labels = {
        card.id: f"{STAGE_LABELS[card.stage.value]} · {card.course} · {card.name}"
        for card in cards
    }
    card_ids = [card.id for card in cards]
    current_id = st.session_state.engine.card.id
    index = card_ids.index(current_id) if current_id in card_ids else 0
    selected = st.selectbox(
        "学段 / 课程 / 卡片",
        card_ids,
        index=index,
        format_func=lambda card_id: labels[card_id],
        key="card_selector",
    )
    if selected != current_id:
        selected_card = next(card for card in cards if card.id == selected)
        st.session_state.pop("similar_state", None)
        with st.spinner("正在加载卡片…"):
            st.session_state.engine = SessionEngine(
                card=selected_card,
                provider=st.session_state.provider,
                repository=st.session_state.repository,
                consent=st.session_state.consent,
            )
        st.rerun()


def _render_answer_input(exercise: Exercise, key_suffix: str | None = None) -> str:
    """按题型渲染答题控件并返回原始输入。"""
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


def _render_update_section() -> None:
    """渲染版本信息与更新检查入口。"""
    with st.expander("关于与更新", expanded=False):
        st.caption(f"版本 {mathcoach.__version__}")
        if st.button("检查更新", key="check_update", icon=ICON_UPDATE):
            placeholder = st.empty()
            placeholder.markdown(":shimmer[正在检查更新…]")
            try:
                release = check_for_update(mathcoach.__version__)
            except UpdateCheckError:
                st.session_state.update_notice = ("error", None)
            else:
                st.session_state.update_notice = (
                    ("current", None) if release is None else ("update", release)
                )
            finally:
                placeholder.empty()
        notice = st.session_state.get("update_notice")
        if notice is None:
            return
        status, release = notice
        if status == "error":
            st.caption("无法检查更新（离线或网络不可用）。")
        elif status == "current":
            st.caption("已是最新版本。")
        elif release is not None:
            st.success(f"{ICON_UPDATE} 发现新版本 {release.version}")
            if release.notes:
                st.caption(release.notes[:200])
            st.link_button("打开下载页", release.page_url)


def _render_sidebar() -> None:
    """渲染侧栏：卡片选择、功能切换与同意开关。"""
    consent: Consent = st.session_state.consent
    repository = st.session_state.repository
    with st.sidebar:
        st.header("学习设置")
        _render_card_selector()
        if (
            st.query_params.get("grade")
            and st.session_state.get("app_mode") != MODE_GRADE
        ):
            st.session_state["app_mode"] = MODE_GRADE

        def _on_mode_change() -> None:
            """离开按年级模式时清掉 grade 查询参数。"""
            if (
                st.session_state.get("app_mode") != MODE_GRADE
                and st.query_params.get("grade")
            ):
                st.query_params.pop("grade", None)

        st.selectbox(
            "功能",
            MODES,
            key="app_mode",
            on_change=_on_mode_change,
        )
        st.caption(
            f"当前卡片：{st.session_state.engine.card.name} · "
            f"课程：{st.session_state.engine.card.course}"
        )
        memory = st.toggle(
            "保存学习收据（本机）", value=consent.memory, key="consent_memory"
        )
        mistake_book = st.toggle(
            "记录错题本（本机）", value=consent.mistake_book, key="consent_book"
        )
        st.toggle("显示叙事层", value=True, key="narrative_enabled")
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
            st.info(f"{ICON_INFO} 游客模式：本次学习数据只存在内存中。")
        st.divider()
        if st.button("重置会话", key="reset_session", icon=ICON_RESTART):
            st.session_state.pop("similar_state", None)
            st.session_state.engine = SessionEngine(
                card=st.session_state.engine.card,
                provider=st.session_state.provider,
                repository=st.session_state.repository,
                consent=st.session_state.consent,
            )
            st.rerun()


def _render_mistake_tab() -> None:
    """渲染错题本的统计、错题与复习清单。"""
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    st.subheader("错题本")
    if not consent.mistake_book:
        st.info(f"{ICON_INFO} 错题本已关闭。")
        return
    entries = repository.list_mistakes(limit=None)
    pending = sum(
        1 for entry in entries if entry.review_state is not ReviewState.MASTERED
    )
    today_end = end_of_local_day(datetime.now(timezone.utc))
    due_today = sum(
        1
        for item in repository.list_review_items()
        if item.due_at <= today_end
    )
    kpi_row(
        [
            ("错题总数", str(len(entries))),
            ("待复习", str(pending)),
            ("今天到期", str(due_today)),
        ]
    )
    _render_mistake_book(repository)
    _render_review_plan(repository)


def _render_settings_tab() -> None:
    """渲染设置页并在末尾附更新检查。"""
    render_settings_page(
        st.session_state.repository,
        st.session_state.consent,
        st.session_state.provider,
    )
    _render_update_section()


def _render_hint_actions() -> None:
    """渲染提示按钮组。"""
    with st.expander("需要提示？"):
        if st.button("给步骤（最高 L4）", key="hint_step", icon=ICON_HINT):
            engine.request_hint("step")
            st.rerun()
        if st.button("直接给答案（最高 L4）", key="hint_answer", icon=ICON_HINT):
            engine.request_hint("answer")
            st.rerun()
        if st.button(
            "开放 L5（需先尝试 L1—L4）", key="hint_level5", icon=ICON_HINT
        ):
            engine.request_hint("level5")
            st.rerun()


def _render_knowledge_entry(card: KnowledgeCard) -> None:
    """答题前入口：打开当前卡片的学习卡片，不阻塞做题。"""
    if not load_learning_cards_enabled(st.session_state.consent):
        return
    if st.button(
        "先学习此知识点",
        key=f"knowledge_entry_{card.id}",
        icon=ICON_INFO,
    ):
        st.query_params["kp"] = card.id
        st.rerun()


def _prerequisite_chain_text(
    prerequisites: tuple[PrerequisiteRef, ...], current_name: str
) -> str:
    """把先修链从基础到当前知识点拼成一行。"""
    if not prerequisites:
        return "无"
    names = [item.name for item in reversed(prerequisites)]
    return " → ".join(names + [current_name])


def _render_knowledge_context(
    card: KnowledgeCard, exercise: Exercise
) -> None:
    """答错后先定位知识点，不提前泄露标准答案。"""
    explanation = build_explanation(
        card, exercise, _load_knowledge_tree()
    )
    st.markdown("**知识点定位**")
    st.markdown(
        f"- 知识点：{explanation.knowledge_point_name}"
        f"（{explanation.course}）\n"
        f"- 概念回看：{explanation.definition}"
    )
    if explanation.common_mistakes:
        st.markdown(
            "- 常见误区：" + "；".join(explanation.common_mistakes)
        )
    st.caption(
        "先修链："
        + _prerequisite_chain_text(
            explanation.prerequisites, explanation.knowledge_point_name
        )
    )


def _render_error_localization(
    card: KnowledgeCard, error_type: ErrorType
) -> ErrorLocalization:
    """把已确认的错因落到知识点与先修链上。"""
    localization = locate_error(
        card, error_type, _load_knowledge_tree()
    )
    st.markdown("**错因定位**")
    st.markdown(
        f"- 知识点：{localization.knowledge_point_name}"
        f"（{localization.course}）\n"
        f"- 错因：{localization.error_type.value}"
        f"——{localization.reason}\n"
        f"- 建议先复习：{localization.review_name}"
    )
    st.caption(f"补法：{localization.suggestion}")
    st.caption(
        "先修链："
        + _prerequisite_chain_text(
            localization.prerequisites, localization.knowledge_point_name
        )
    )
    return localization


def _render_diagnosis_actions(
    card: KnowledgeCard, localization: ErrorLocalization
) -> None:
    """诊断结论后的下一步：打开先修卡、学习卡片或练同类题。"""
    left, right = st.columns(2)
    if localization.review_id != card.id:
        if left.button(
            f"去复习先修卡：{localization.review_name}",
            key=f"diagnosis_review_{localization.review_id}",
            icon=ICON_BOOK,
        ):
            st.query_params["kp"] = localization.review_id
            st.rerun()
    if right.button(
        "看学习卡片",
        key="diagnosis_learning_card",
        icon=ICON_BOOK,
    ):
        st.query_params["kp"] = card.id
        st.rerun()
    similar_questions = build_similar_questions(
        card, {engine.current_exercise.id}
    )
    if similar_questions and st.button(
        f"练同类题（{len(similar_questions)} 题）",
        key="diagnosis_similar",
        icon=ICON_PLAY,
    ):
        st.session_state.similar_state = DailyState(
            date_key=f"similar-{time.time_ns()}",
            questions=similar_questions,
            started_at=datetime.now(timezone.utc),
        )
        st.rerun()


def _render_similar_practice() -> None:
    """诊断后的小复习包：只练同卡其他题，答完可回到诊断。"""
    state: DailyState | None = st.session_state.get("similar_state")
    if state is None:
        st.info(f"{ICON_INFO} 暂无同类练习，请先回到卡片诊断错因。")
        return
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    st.subheader("同类练习")
    st.caption(
        f"{engine.card.name} · 共 {len(state.questions)} 题，"
        "答完自动结算，不影响当前诊断。"
    )

    def _on_submission(
        submission: DailySubmission, answer: str, moment: datetime
    ) -> None:
        """答对登记独立复习，答错登记复习并写入错题本。"""
        if submission.correct is True:
            _record_review_write(submission.question.exercise.id, True)
        elif submission.correct is False:
            _record_review_write(submission.question.exercise.id, False)
            record_daily_mistake(
                repository, consent, submission.question, answer, moment
            )

    _render_active_quiz(
        state,
        key_prefix="similar",
        on_submission=_on_submission,
        summary_title="同类练习完成",
    )
    if state.finished and st.button(
        "回到诊断",
        key="similar_back",
        icon=ICON_RESTART,
    ):
        st.session_state.pop("similar_state", None)
        st.rerun()


def _render_explanation(card: KnowledgeCard, exercise: Exercise) -> None:
    """渲染完整解析、常见误区与先修链。"""
    explanation = build_explanation(
        card, exercise, _load_knowledge_tree()
    )
    st.markdown("**完整解析**")
    st.markdown(
        f"- 标准答案：{explanation.answer}\n"
        f"- 解题思路：{explanation.solution_outline}"
    )
    if explanation.common_mistakes:
        st.markdown(
            "- 常见误区：" + "；".join(explanation.common_mistakes)
        )
    st.caption(
        "先修链："
        + _prerequisite_chain_text(
            explanation.prerequisites, explanation.knowledge_point_name
        )
    )


def _render_restatement(receipt: Receipt) -> None:
    """收据页的 L6 费曼复述：记录前提供输入，记录后展示质量。"""
    if receipt.restatement_quality:
        text = (
            f"L6 复述质量：{receipt.restatement_quality}"
            "（按标准思路的关键片段覆盖）"
        )
        if receipt.restatement_quality == RESTATEMENT_SPARSE:
            text += "；有错题记录的题目会按半独立复习"
        st.caption(text)
        return
    st.markdown("**L6 费曼复述（可选）**")
    restatement = st.text_area(
        "用自己的话复述本题思路",
        key=f"restatement_{receipt.exercise_id}",
        height=80,
    )
    if st.button(
        "提交复述",
        key="submit_restatement",
        icon=ICON_SUBMIT,
    ):
        try:
            engine.submit_restatement(restatement)
        except ValueError as exc:
            st.warning(f"{ICON_INFO} {exc}")
        else:
            st.rerun()


def _render_session() -> None:
    """按当前阶段渲染陪练主流程。"""
    view = engine.view
    if view.phase in (Phase.GOAL_CONFIRM, Phase.EXPLAIN):
        render_dynamic_background(st.session_state.consent, "empty")

    if view.phase is Phase.GOAL_CONFIRM:
        with card(view.title):
            st.write(math_markdown(view.body))
            with st.form(
                "goal_form",
                clear_on_submit=False,
                enter_to_submit=False,
                border=False,
            ):
                goal = st.text_input(
                    "今天想练到什么？", key="goal_input"
                )
                submitted = st.form_submit_button(
                    "确认目标",
                    key="confirm_goal",
                    icon=ICON_PLAY,
                    **button_kwargs(PRIMARY),
                )
            if submitted:
                try:
                    with loading_skeleton(SKELETON_CARD):
                        engine.confirm_goal(goal)
                except Blocked:
                    st.error(f"{ICON_ERROR} {REFUSAL_TEXT}")
                except ValueError as exc:
                    st.error(f"{ICON_ERROR} {exc}")
                else:
                    st.rerun()
        return

    if view.phase is Phase.EXPLAIN:
        with card(view.title, engine.card.course):
            st.write(math_markdown(view.body))
            if view.notice:
                st.info(f"{ICON_INFO} {view.notice}")
            # 可视化是可选增强：失败时只提示，不阻断讲解/小测
            if render_visual(engine.card.id) == "failed":
                st.info(f"{ICON_INFO} 可视化暂不可用")
            kpi_row(
                [
                    ("当前卡片", engine.card.name),
                    ("课程", engine.card.course),
                    ("难度", engine.card.difficulty.value),
                ]
            )
            if st.button(
                "开始小测",
                key="begin_quiz",
                icon=ICON_PLAY,
                **button_kwargs(PRIMARY),
            ):
                engine.begin_quiz()
                st.rerun()
            _render_knowledge_entry(engine.card)
        return

    if view.phase is Phase.QUIZ:
        with card(view.title):
            total = len(engine.card.exercises)
            position = next(
                (
                    index + 1
                    for index, exercise in enumerate(engine.card.exercises)
                    if exercise.id == engine.state.exercise_id
                ),
                1,
            )
            st.progress(
                position / total if total else 0.0,
                text=f"第 {position} / {total} 题",
            )
            if view.notice:
                st.caption(view.notice)
            if render_visual(engine.card.id) == "failed":
                st.info(f"{ICON_INFO} 可视化暂不可用")
            st.write(math_markdown(view.body))
            answer = _render_answer_input(engine.current_exercise)
            if st.button(
                "提交答案",
                key="submit_answer",
                icon=ICON_SUBMIT,
                **button_kwargs(PRIMARY),
            ):
                next_view = engine.submit_answer(answer)
                if next_view.phase is Phase.RECEIPT:
                    queue_feedback("correct", st.session_state.consent)
                elif next_view.phase in (
                    Phase.HINT,
                    Phase.DIAGNOSE,
                    Phase.WRAPUP,
                ):
                    queue_feedback("wrong", st.session_state.consent)
                celebrate_five_correct(
                    engine, st.session_state.consent
                )
                st.rerun()
        _render_hint_actions()
        return

    if view.phase is Phase.DIAGNOSE:
        with card(view.title):
            st.error(f"{ICON_ERROR} 再看一眼提示")
            st.write(math_markdown(view.body))
            if view.notice:
                st.info(f"{ICON_INFO} {view.notice}")
            if engine.state.diagnosis is not None:
                localization = _render_error_localization(
                    engine.card, engine.state.diagnosis
                )
                _render_diagnosis_actions(engine.card, localization)
            else:
                _render_knowledge_context(
                    engine.card, engine.current_exercise
                )
            selected = st.radio(
                "选择更贴近的错因",
                view.options,
                key=f"diagnosis_{engine.state.exercise_id}_{len(engine.state.attempts)}",
            )
            if st.button(
                "确认错因",
                key="confirm_diagnosis",
                icon=ICON_CHECK,
                **button_kwargs(PRIMARY),
            ):
                engine.confirm_diagnosis(selected)
                st.rerun()
        return

    if view.phase is Phase.HINT:
        current_id = engine.state.exercise_id
        if any(
            attempt["exercise_id"] == current_id
            and attempt.get("correct") is False
            for attempt in engine.state.attempts
        ):
            st.error(f"{ICON_ERROR} 再看一眼提示")
        hint_block(engine.state.hint_level, math_markdown(view.body))
        if view.notice:
            st.caption(view.notice)
        if engine.state.hint_level >= 4:
            _render_explanation(engine.card, engine.current_exercise)
        elif engine.state.diagnosis is not None:
            _render_error_localization(
                engine.card, engine.state.diagnosis
            )
        else:
            _render_knowledge_context(
                engine.card, engine.current_exercise
            )
        if st.button("再试一次", key="retry", icon=ICON_RESTART):
            engine.retry()
            st.rerun()
        _render_hint_actions()
        return

    if view.phase is Phase.RECEIPT:
        receipt = view.receipt
        mark_first_use_done()
        with card("收据已生成"):
            st.success(f"{ICON_CHECK} 答对了")
            if receipt is not None:
                st.caption(f"题型：{receipt.exercise_type.value}")
                kpi_row(
                    [
                        ("用时", f"{receipt.duration_s} 秒"),
                        ("最高提示层级", f"L{receipt.max_hint_level}"),
                        ("独立程度", receipt.independence.value),
                    ]
                )
                if receipt.basis:
                    st.caption(f"依据：{receipt.basis}")
                _render_restatement(receipt)
            # 叙事层可关闭；关闭后只隐藏展示，不影响收据与统计
            if (
                st.session_state.get("narrative_enabled", True)
                and narrative_nodes
            ):
                progress = _narrative_progress(st.session_state.repository)
                upcoming = next_node(progress, narrative_nodes)
                if upcoming is None:
                    st.caption("叙事：本段旅程已全部点亮。")
                else:
                    st.caption(f"叙事：下一节点「{upcoming.name}」等待解锁。")
            _render_explanation(engine.card, engine.current_exercise)
        if st.button(
            "继续",
            key="advance",
            icon=ICON_PLAY,
            **button_kwargs(PRIMARY),
        ):
            next_view = engine.advance()
            if next_view.phase is Phase.WRAPUP:
                queue_feedback("complete", st.session_state.consent)
            st.rerun()
        return

    if view.phase is Phase.WRAPUP:
        with card("本次闭环完成"):
            st.write(math_markdown(view.body))
            _render_explanation(engine.card, engine.current_exercise)
            tree = _load_knowledge_tree()
            if tree is not None:
                render_learning_status(
                    learning_status_for(
                        st.session_state.repository,
                        engine.card.id,
                        tree,
                    )
                )
            if st.button("重新开始", key="restart", icon=ICON_RESTART):
                st.session_state.engine = SessionEngine(
                    card=engine.card,
                    provider=provider,
                    repository=st.session_state.repository,
                    consent=st.session_state.consent,
                )
                st.rerun()
        return


def _mastery_rows(repository: Repository) -> list[tuple[str, str]]:
    """把 BKT 概率整理成现有仪表盘上的掌握度列表。"""
    receipts = repository.list_receipts(limit=None)
    mistakes = repository.list_mistakes(limit=None)
    card_ids = sorted(
        {receipt.card_id for receipt in receipts}
        | {mistake.card_id for mistake in mistakes}
    )
    rows: list[tuple[str, str]] = []
    for card_id in card_ids:
        probability = repository.get_mastery(card_id)
        if probability is None:
            probability = initial_mastery()
        receipt_count = sum(1 for receipt in receipts if receipt.card_id == card_id)
        wrong_count = sum(1 for mistake in mistakes if mistake.card_id == card_id)
        rows.append(
            (
                card_id,
                basis_for_mastery(
                    receipt_count,
                    wrong_count,
                    receipt_count + wrong_count,
                    probability,
                ),
            )
        )
    return rows


def _narrative_progress(repository: Repository) -> NarrativeProgress:
    """用已完成卡片计算叙事进度。"""
    receipts = repository.list_receipts(limit=None)
    completed_cards = {receipt.card_id for receipt in receipts}
    return build_progress(narrative_nodes, completed_cards)


def _next_recommendations(
    repository: Repository,
    cards: list[KnowledgeCard],
    prerequisites: dict[str, list[str]],
) -> list[Recommendation]:
    """按先修复拓扑顺序与 BKT 掌握度推荐 3 张未掌握卡片，错题卡优先。"""
    receipts = repository.list_receipts(limit=None)
    mistakes = repository.list_mistakes(limit=None)
    completed = {receipt.exercise_id for receipt in receipts}
    mastered = {
        card.id
        for card in cards
        if card.exercises and all(exercise.id in completed for exercise in card.exercises)
    }
    weak_cards = {
        mistake.card_id
        for mistake in mistakes
        if mistake.review_state is not ReviewState.MASTERED
    }
    mastery = {
        card.id: probability
        for card in cards
        if (probability := repository.get_mastery(card.id)) is not None
    }
    return recommend(
        [card.id for card in cards],
        prerequisites,
        mastered,
        weak_cards,
        limit=3,
        mastery=mastery,
    )


def _start_card_session(card_id: str) -> None:
    """切换到指定卡片并回到陪练页。"""
    selected_card = next(card for card in cards if card.id == card_id)
    st.session_state.pop("similar_state", None)
    st.session_state.engine = SessionEngine(
        card=selected_card,
        provider=st.session_state.provider,
        repository=st.session_state.repository,
        consent=st.session_state.consent,
    )
    st.session_state["card_selector"] = selected_card.id
    st.session_state["app_mode"] = MODE_SESSION
    st.session_state["main_tabs"] = "当前任务"


def _render_dashboard() -> None:
    """渲染学习仪表盘与下一步推荐。"""
    render_dynamic_background(st.session_state.consent)
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
    mastery_rows = _mastery_rows(st.session_state.repository)
    if mastery_rows:
        st.markdown("**掌握概率**")
        for card_id, text in mastery_rows:
            st.markdown(f"- {card_id}")
            st.caption(f"依据：{text}")
    recommendations = _next_recommendations(
        st.session_state.repository, cards, prerequisites
    )
    if recommendations:
        st.markdown("**下一步推荐**")
        for recommendation in recommendations:
            st.markdown(
                f"- {recommendation.card_id}：{recommendation.reason}"
            )
            st.caption(f"依据：{recommendation.basis}")
        first_card = next(
            card for card in cards if card.id == recommendations[0].card_id
        )
        st.button(
            f"推荐开始：{first_card.name}",
            key="start_recommended",
            icon=ICON_PLAY,
            on_click=_start_card_session,
            args=(first_card.id,),
            **button_kwargs(PRIMARY),
        )
    if st.session_state.get("narrative_enabled", True) and narrative_nodes:
        progress = _narrative_progress(st.session_state.repository)
        st.markdown("**叙事进度**")
        unlocked = set(progress.unlocked)
        for node in narrative_nodes:
            if node.id in unlocked:
                st.markdown(f"- **{node.name}**：{node.description}")
        upcoming = next_node(progress, narrative_nodes)
        if upcoming is None:
            st.caption("叙事线已完成。")
        else:
            st.caption(f"下一节点：{upcoming.name}")
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
    gaps = _collect_gaps(st.session_state.repository)
    if gaps:
        _render_gap_diagnosis(gaps)
    if summary.receipts == 0 and summary.mistakes == 0:
        st.info(f"{ICON_INFO} 还没有学习记录，先完成一次讲解 → 小测闭环。")


def _render_quiz_summary(state: DailyState, now: datetime, title: str) -> None:
    """渲染限时小测的结算摘要。"""
    used = min(state.time_limit_s, elapsed_seconds(state, now))
    st.success(
        f"{ICON_CHECK} {title}：{state.correct}/{len(state.questions)} 正确，"
        f"用时 {used} 秒。"
    )
    if state.timed_out:
        st.caption("时间到，未作答题目不计分。")
    if state.feedback:
        st.info(f"{ICON_INFO} {state.feedback}")


@st.fragment(run_every=5)
def _render_quiz_countdown(state: DailyState) -> None:
    """只刷新倒计时文本，避免整页周期性重跑。"""
    now = datetime.now(timezone.utc)
    if time_is_up(state, now):
        st.caption("时间到，提交当前答案后结算。")
        return
    st.caption(
        f"剩余 {remaining_seconds(state, now)} 秒 · "
        f"第 {state.index + 1}/{len(state.questions)} 题"
    )


def _render_active_quiz(
    state: DailyState,
    *,
    key_prefix: str,
    on_submission: Callable[[DailySubmission, str, datetime], None] | None = None,
    on_finish: Callable[[DailyState, datetime], None] | None = None,
    summary_title: str = "挑战结束",
) -> None:
    """渲染进行中的限时小测；超时自动结算。"""
    now = datetime.now(timezone.utc)
    if not state.finished and time_is_up(state, now):
        finish_daily(state, now, timed_out=True)
    if state.finished:
        if not state.persisted and on_finish is not None:
            on_finish(state, now)
            state.persisted = True
        _render_quiz_summary(state, now, summary_title)
        completed_key = f"feedback_complete:{key_prefix}:{state.date_key}"
        if not st.session_state.get(completed_key):
            st.session_state[completed_key] = True
            queue_feedback("complete", st.session_state.consent)
        return

    _render_quiz_countdown(state)
    if state.feedback:
        st.info(f"{ICON_INFO} {state.feedback}")
    question = current_question(state)
    if question is None:
        return
    st.markdown(f"**{question.card.course} · {question.card.name}**")
    st.write(question.exercise.stem)
    answer = _render_answer_input(
        question.exercise, key_suffix=f"{key_prefix}_{state.index}"
    )
    if st.button(
        "提交答案",
        key=f"{key_prefix}_submit",
        icon=ICON_SUBMIT,
        **button_kwargs(PRIMARY),
    ):
        submission = submit_daily_answer(state, answer, now)
        if submission is not None:
            if on_submission is not None:
                on_submission(submission, answer, now)
            if submission.correct is True:
                queue_feedback("correct", st.session_state.consent)
            elif submission.correct is False:
                queue_feedback("wrong", st.session_state.consent)
        if state.finished and on_finish is not None and not state.persisted:
            on_finish(state, now)
            state.persisted = True
        st.rerun()


def _render_daily_challenge() -> None:
    """渲染每日挑战；同一天只展示一次结果。"""
    now = datetime.now(timezone.utc)
    day_key = local_day_key(now)
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
            f"{ICON_CHECK} 今天的挑战已完成：{result.correct}/{result.total} 正确，"
            f"用时 {result.duration_s} 秒。"
        )
        st.caption("明天再来。")
        return

    if state is None:
        st.write("5 道跨模块小题，限时 5 分钟。答错会自动进入错题本。")
        if st.button(
            "开始 5 分钟挑战",
            key="start_daily",
            icon=ICON_PLAY,
            **button_kwargs(PRIMARY),
        ):
            st.session_state.daily_state = DailyState(
                date_key=day_key,
                questions=build_daily_questions(cards, local_day(now)),
                started_at=now,
            )
            st.rerun()
        return

    def _on_submission(
        submission: DailySubmission, answer: str, moment: datetime
    ) -> None:
        """答错时写入错题本。"""
        if submission.correct is False:
            record_daily_mistake(
                repository, consent, submission.question, answer, moment
            )

    def _on_finish(finished_state: DailyState, moment: datetime) -> None:
        """保存每日挑战结果。"""
        save_daily_result(repository, consent, finished_state, moment)

    _render_active_quiz(
        state,
        key_prefix=f"daily_{day_key}",
        on_submission=_on_submission,
        on_finish=_on_finish,
    )


def _render_challenge() -> None:
    """渲染挑战赛与本地最好成绩。"""
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
        if st.button(
            "开始挑战赛",
            key="start_challenge",
            icon=ICON_PLAY,
            **button_kwargs(PRIMARY),
        ):
            st.session_state.challenge_state = build_challenge_state(
                cards, now, time.time_ns()
            )
            st.rerun()
        return

    def _on_submission(
        submission: DailySubmission, answer: str, moment: datetime
    ) -> None:
        """答错时写入错题本。"""
        if submission.correct is False:
            record_daily_mistake(
                repository, consent, submission.question, answer, moment
            )

    def _on_finish(finished_state: DailyState, moment: datetime) -> None:
        """保存挑战赛结果。"""
        save_challenge_result(repository, consent, finished_state, moment)

    _render_active_quiz(
        state,
        key_prefix="challenge",
        on_submission=_on_submission,
        on_finish=_on_finish,
        summary_title="挑战赛结束",
    )
    if state.finished and st.button(
        "再来一局", key="restart_challenge", icon=ICON_RESTART
    ):
        st.session_state.pop("challenge_state", None)
        st.rerun()


def _render_learning_path() -> None:
    """渲染按课程分组的完成度与下一张建议。"""
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
            f"{ICON_PLAY} 建议下一张：{STAGE_LABELS[card.stage.value]} · "
            f"{card.course} · {card.name}（{path.recommended_reason}）"
        )
    else:
        st.success(f"{ICON_CHECK} {path.recommended_reason}")

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
    """渲染最近 7 天的周报与错因趋势。"""
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

    st.markdown("**掌握度变化**")
    if report.mastery_changes:
        for change in report.mastery_changes:
            st.markdown(
                f"- {change.card_id}：{change.before:.0%} → "
                f"{change.after:.0%}（{change.delta:+.0%}）"
            )
    else:
        st.caption("本周暂无掌握度变化记录。")

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
    """校验写入门后记录一次复习结果。"""
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    now = datetime.now(timezone.utc)
    try:
        assert_write_allowed("review", consent=consent)
    except (WriteBlocked, ConfirmationRequired) as exc:
        repository.record_audit("review", f"blocked:{exc.reason}")
        st.warning("写操作被安全规则拦截。")
        return
    quality = quality_from_independence(independent)
    updated = repository.record_review(
        exercise_id, independent=quality, now=now
    )
    if updated is not None:
        repository.record_mastery(
            updated.card_id,
            correct=independent,
            now=now,
            quality=quality,
        )
    repository.record_audit("review", "ok")


def _render_review_package() -> None:
    """渲染智能复习包；错题本关闭时直接提示。"""
    now = datetime.now(timezone.utc)
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    st.subheader("智能复习包 · 15 分钟 5 题")
    if not consent.mistake_book:
        st.info(f"{ICON_INFO} 错题本已关闭，无法生成复习包。")
        return

    state: DailyState | None = st.session_state.get("review_state")
    if state is None:
        with loading_skeleton(SKELETON_CARD):
            gaps = _collect_gaps(repository)
            priority = {gap.chain[-1] for gap in gaps}
            new_ratio = current_settings(
                st.session_state.consent
            ).new_review_ratio
            package = build_review_package(
                repository,
                cards,
                now,
                priority_card_ids=priority,
                new_ratio=new_ratio,
            )
        if gaps:
            _render_gap_diagnosis(gaps)
        if not package.questions:
            st.info(f"{ICON_INFO} {package.reason}")
            return
        st.write(package.reason)
        if st.button(
            "开始复习包",
            key="start_review",
            icon=ICON_PLAY,
            **button_kwargs(PRIMARY),
        ):
            st.session_state.review_state = DailyState(
                date_key=f"review-{time.time_ns()}",
                questions=package.questions,
                started_at=now,
                time_limit_s=REVIEW_PACKAGE_LIMIT_S,
            )
            st.rerun()
        return

    def _on_submission(
        submission: DailySubmission, answer: str, moment: datetime
    ) -> None:
        """答对记为独立复习，答错记复习并写入错题本。"""
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
    if state.finished:
        mark_first_use_done()
        celebrate_review_complete(state, st.session_state.consent)
    if state.finished and st.button(
        "再来一组", key="restart_review", icon=ICON_RESTART
    ):
        st.session_state.pop("review_state", None)
        st.rerun()


def _mistake_variants(
    entry: MistakeEntry, exercises_by_id: dict[str, Exercise]
) -> list[str]:
    """取错题的变式，旧数据回退到题目快照。"""
    variants = entry.exercise_snapshot.get("variants") or []
    if variants:
        return list(variants)
    exercise = exercises_by_id.get(entry.exercise_id)
    return list(exercise.variants) if exercise else []


def _render_variant_practice() -> None:
    """渲染错题变式练习与掌握按钮。"""
    st.subheader("错题变式")
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    if not consent.mistake_book:
        st.info(f"{ICON_INFO} 错题本已关闭，无法练习变式。")
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
        st.info(f"{ICON_INFO} 还没有带变式的错题。先在陪练或每日挑战中答错一题。")
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
    if left.button("我已独立完成", key="variant_done", icon=ICON_CHECK):
        _record_review_write(entry.exercise_id, True)
        st.rerun()
    if right.button("仍需复习", key="variant_retry", icon=ICON_REVIEW):
        _record_review_write(entry.exercise_id, False)
        st.rerun()


def _render_export() -> None:
    """渲染导出目录、预览与确认流程。"""
    st.subheader("导出学习包")
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    if not (consent.memory or consent.mistake_book):
        st.info(f"{ICON_INFO} 游客模式不可导出，请先开启本机记忆或错题本。")
        return

    default_dir = str(Path.home() / "mathcoach-exports")
    directory = st.text_input("导出目录", value=default_dir, key="export_dir")
    now = datetime.now(timezone.utc)
    with loading_skeleton(SKELETON_PANEL):
        artifact = build_export_artifact(
            repository, cards, Path(directory), now
        )

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
    if st.button(
        "确认导出",
        key="confirm_export",
        icon=ICON_EXPORT,
        **button_kwargs(PRIMARY),
    ):
        try:
            written = write_export(
                artifact,
                consent=consent,
                confirmation=confirmation,
                repository=repository,
            )
        except ConfirmationRequired:
            st.error(f"{ICON_ERROR} 导出未执行：请输入完整确认语句“我确认执行此操作”。")
        except WriteBlocked as exc:
            st.error(f"{ICON_ERROR} 导出未执行：{exc.reason}")
        except OSError as exc:
            st.error(
                f"{ICON_ERROR} 导出失败：无法写入 {directory}"
                f"（{exc.strerror or exc}）。"
            )
        else:
            st.success(f"{ICON_CHECK} 已导出 {len(written)} 个文件到 {directory}")


def _render_grade_mode(initial_grade: str | None = None) -> None:
    """渲染按年级浏览页面。"""
    index = _load_grade_index()
    if index is None:
        return
    spans = _load_grade_spans() or {}
    render_grade_page(
        cards=cards,
        index=index,
        spans=spans,
        repository=st.session_state.repository,
        consent=st.session_state.consent,
        initial_grade=initial_grade,
    )


def _render_current_mode() -> None:
    """按查询参数或侧栏选项渲染当前页面。"""
    focus = st.query_params.get("kp")
    if isinstance(focus, list):
        focus = focus[0] if focus else None
    if focus:
        render_knowledge_browser(
            cards=cards,
            provider=provider,
            repository=st.session_state.repository,
            consent=st.session_state.consent,
            focus_id=focus,
        )
        return
    grade = st.query_params.get("grade")
    if isinstance(grade, list):
        grade = grade[0] if grade else None
    if grade:
        st.session_state["_last_rendered_mode"] = MODE_GRADE
        _render_grade_mode(grade)
        return
    mode = st.session_state.get("app_mode", MODE_SESSION)
    if (
        mode == MODE_SESSION
        and st.session_state.get("similar_state") is not None
    ):
        st.session_state["_last_rendered_mode"] = mode
        _render_similar_practice()
        return
    previous_mode = st.session_state.get("_last_rendered_mode")
    if mode == MODE_GRADE and previous_mode != MODE_GRADE:
        fallback = load_default_grade(st.session_state.consent)
        st.session_state["grade_filter"] = st.session_state.get(
            "grade_last_selected", fallback
        )
    st.session_state["_last_rendered_mode"] = mode
    if mode == MODE_GRADE:
        _render_grade_mode()
    elif mode == MODE_DASHBOARD:
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


_render_sidebar()

st.title("数学陪练")
if isinstance(provider, OfflineProvider) or getattr(provider, "degraded", False):
    st.caption("离线模板模式：讲解使用确定性模板，判分逻辑不变。")
render_onboarding(
    st.session_state.consent,
    had_history=st.session_state["onboarding_had_history"],
)

tabs = st.tabs(
    ["当前任务", "学习档案", "错题本", "设置"],
    default="当前任务",
    key="main_tabs",
    on_change="rerun",
)
with tabs[0]:
    if tabs[0].open:
        _render_current_mode()
with tabs[1]:
    if tabs[1].open:
        _render_dashboard()
with tabs[2]:
    if tabs[2].open:
        _render_mistake_tab()
with tabs[3]:
    if tabs[3].open:
        _render_settings_tab()

play_pending_feedback(st.session_state.consent)
play_pending_celebration(st.session_state.consent)
inject_micro_interactions(st.session_state.consent)
