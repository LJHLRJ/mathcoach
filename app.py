"""Streamlit 单页装配：只渲染 session 层给的视图，不写判定逻辑。"""
import sqlite3
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

import mathcoach
from mathcoach.analytics import (
    TemplateNarrator,
    build_attribution,
    build_narrator,
)
from mathcoach.board import BOARD_FRAMES, BoardFrameSpec, render_frame
from mathcoach.mastery import (
    WEAK_KC_THRESHOLD,
    RepairPlan,
    build_kc_progress,
    build_repair_plan,
    observation_weight,
    quality_for_correct,
    reference_seconds_from_history,
    weak_kc_recommendations,
)
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
from mathcoach.domain.dependence import (
    DependenceDialogEvent,
    DependenceLevel,
    DependenceSignal,
    DependenceStepAttempt,
    DependenceStepRun,
    evaluate_dependence,
)
from mathcoach.domain.diagnosis import Diagnosis, diagnose
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
from mathcoach.domain.judge import evaluate
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
from mathcoach.domain.representation import Representation
from mathcoach.domain.scaffold import stage_for_level
from mathcoach.domain.spaced_repetition import quality_from_independence
from mathcoach.export.package import (
    build_export_artifact,
    describe_export,
    write_export,
)
from mathcoach.insights import build_step_insights
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
from mathcoach.planner import (
    build_plan as build_worksheet_plan,
    plan_to_worksheet,
    render_plan_markdown,
)
from mathcoach.paths import PATHS, SolutionPath, check_checkpoint
from mathcoach.recall import (
    RecallQuery,
    RecallStore,
    query_from_mistake,
    recall_similar,
)
from mathcoach.representation import (
    RepresentationRecorder,
    RepresentationStoreRecorder,
)
from mathcoach.report import (
    ExplainableReport,
    build_explainable_report,
    build_report_client,
    generate_report_narrative,
    render_narrative_markdown,
    render_report_markdown,
)
from mathcoach.scenario import SCENARIOS, render_scenario
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
    DailyQuestion,
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
from mathcoach.steps import (
    STEP_SPECS,
    StepAttempt,
    StepRecorder,
    StepSpec,
    StepStore,
    StepVerdict,
)
from mathcoach.steps.store import step_db_path
from mathcoach.steps.presentation import build_step_reason, present_verdict
from mathcoach.timeutil import end_of_local_day, local_day, local_day_key
from mathcoach.tutor.catalog import KC_BY_ID
from mathcoach.tutor.dialog import (
    DialogEvent,
    DialogStore,
    build_follow_up_client,
    dialog_db_path,
)
from mathcoach.tutor.mastery_store import KCMasteryStore, shadow_db_path
from mathcoach.ui.components import (
    PRIMARY,
    SKELETON_CARD,
    SKELETON_INLINE,
    SKELETON_PANEL,
    button_kwargs,
    loading_skeleton,
    rerun_fragment,
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
from mathcoach.ui.snapshot import RepositorySnapshot
from mathcoach.ui.sound import play_pending_feedback, queue_feedback
from mathcoach.ui.theme import inject_theme
from mathcoach.ui.visuals.registry import (
    get_kc_visual,
    kc_visuals_for_exercises,
    render_kc_visual,
    render_visual,
)
from mathcoach.update_check import UpdateCheckError, check_for_update
from mathcoach.voice import transcribe_and_normalize, voice_available
from mathcoach.worksheet import (
    WorksheetSource,
    build_worksheet,
    render_worksheet_html,
    render_worksheet_markdown,
)

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
MODE_WORKSHEET = "可打印练习单"
MODE_PLANNER = "智能练习册"
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
    MODE_WORKSHEET,
    MODE_PLANNER,
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


def _record_dialog_event(event: DialogEvent) -> None:
    """把追问事件写入独立信号库；游客模式或磁盘异常时静默跳过。"""
    consent: Consent = st.session_state.consent
    if not (consent.memory or consent.mistake_book):
        return
    try:
        with DialogStore() as store:
            store.record(event)
    except (OSError, sqlite3.Error):
        return


def _representation_recorder() -> RepresentationRecorder | None:
    """创建表示降级记录器；游客模式不落库。"""
    consent: Consent = st.session_state.consent
    if not (consent.memory or consent.mistake_book):
        return None
    return RepresentationStoreRecorder()


DEPENDENCE_SIGNAL_KEY = "dependence_signals"


def _empty_dependence_signal(card_id: str) -> DependenceSignal:
    """返回无信号结果；游客模式或读取失败时使用。"""
    return DependenceSignal(level=DependenceLevel.NONE, card_id=card_id)


def _load_dependence_signal(card_id: str) -> DependenceSignal:
    """只读汇总收据、追问与步骤信号，供提示供给决策。"""
    consent: Consent = st.session_state.consent
    if not (consent.memory or consent.mistake_book):
        return _empty_dependence_signal(card_id)
    repository = st.session_state.repository
    try:
        receipts = repository.list_receipts(limit=200)
        mastery = repository.get_mastery(card_id)
    except (OSError, sqlite3.Error):
        return _empty_dependence_signal(card_id)
    dialog_events: list[DependenceDialogEvent] = []
    try:
        if dialog_db_path().exists():
            with DialogStore() as store:
                dialog_events = [
                    DependenceDialogEvent(
                        card_id=event.card_id,
                        level=event.level,
                        kind=event.kind.value,
                        created_at=event.resolved_at,
                    )
                    for event in store.list_events(limit=200)
                ]
    except (OSError, sqlite3.Error):
        dialog_events = []
    step_runs: list[DependenceStepRun] = []
    try:
        if step_db_path().exists():
            with StepStore() as store:
                step_runs = [
                    DependenceStepRun(
                        exercise_id=run.exercise_id,
                        card_id=run.card_id,
                        created_at=run.created_at,
                        attempts=tuple(
                            DependenceStepAttempt(
                                step_index=attempt.step_index,
                                step_tag=attempt.step_tag,
                                verdict=attempt.verdict.value,
                            )
                            for attempt in run.attempts
                        ),
                    )
                    for run in store.list_runs(limit=100)
                ]
    except (OSError, sqlite3.Error):
        step_runs = []
    return evaluate_dependence(
        card_id,
        receipts,
        dialog_events=dialog_events,
        step_runs=step_runs,
        mastery=mastery,
    )


def _cached_dependence_signal(card_id: str) -> DependenceSignal:
    """读取会话内缓存的依赖度信号；缺失时补算。"""
    cache = st.session_state.get(DEPENDENCE_SIGNAL_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[DEPENDENCE_SIGNAL_KEY] = cache
    signal = cache.get(card_id)
    if signal is None:
        signal = _load_dependence_signal(card_id)
        cache[card_id] = signal
    return signal


DEPENDENCE_REASON_LABELS = {
    "semi_independent_streak": "最近几题提示用得较多",
    "semi_independent_density": "最近五题多数用到 L4/L5",
    "dialog_quality_drop": "最近追问命中率低于平时",
    "step_stuck": "同一步骤近期反复出错",
}


def _render_dependence_note(card_id: str) -> None:
    """在收据页展示只读依赖度观察，不改变任何判分。"""
    signal = _cached_dependence_signal(card_id)
    if signal.level is DependenceLevel.NONE:
        return
    labels = [
        DEPENDENCE_REASON_LABELS.get(reason, reason)
        for reason in signal.reasons
    ]
    if labels:
        st.caption("学习自主度观察：" + "；".join(dict.fromkeys(labels)) + "。")


def _render_hint_ceiling_banner(engine: SessionEngine) -> None:
    """展示主动提示上限，并提供随时恢复入口。"""
    if not engine.hint_ceiling_active:
        return
    st.info(
        f"{ICON_INFO} 先自己试一步：主动请求提示暂时只到 "
        f"L{engine.hint_ceiling}；连续两次答错会自动恢复完整提示。"
    )
    if st.button(
        "恢复完整提示",
        key=f"release_ceiling_{engine.card.id}_{engine.state.exercise_id}",
    ):
        engine.release_hint_ceiling("manual")
        st.rerun()


def _build_session_engine(card: KnowledgeCard) -> SessionEngine:
    """创建带追问客户端与事件记录的会话引擎。"""
    provider = st.session_state.provider
    signal = _load_dependence_signal(card.id)
    cache = st.session_state.get(DEPENDENCE_SIGNAL_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[DEPENDENCE_SIGNAL_KEY] = cache
    cache[card.id] = signal
    return SessionEngine(
        card=card,
        provider=provider,
        repository=st.session_state.repository,
        consent=st.session_state.consent,
        dialog_client=build_follow_up_client(provider),
        dialog_recorder=_record_dialog_event,
        representation_recorder=_representation_recorder(),
        hint_ceiling=signal.hint_ceiling,
    )


STEP_VERDICT_LABELS = {
    StepVerdict.CORRECT: "正确",
    StepVerdict.INCORRECT: "这一步不对",
    StepVerdict.UNVERIFIABLE: "无法自动核对",
    StepVerdict.REJECTED: "输入不符合格式",
    StepVerdict.OUT_OF_SCOPE: "超出步骤范围",
}


def _step_recorder() -> StepRecorder:
    """创建步骤记录器；游客模式或磁盘异常时只判定不落库。"""
    consent: Consent = st.session_state.consent
    if not (consent.memory or consent.mistake_book):
        return StepRecorder(enabled=False)
    try:
        store = StepStore()
    except (OSError, sqlite3.Error):
        return StepRecorder(enabled=False)
    try:
        kc_store = KCMasteryStore()
    except (OSError, sqlite3.Error):
        return StepRecorder(store=store)
    return StepRecorder(store=store, kc_store=kc_store)


def _step_state_key(engine: SessionEngine) -> str:
    """按会话与题目定位分步填写状态。"""
    started = (
        engine.state.started_at.isoformat()
        if engine.state.started_at is not None
        else "none"
    )
    return f"step_state_{engine.current_exercise.id}_{started}"


def _render_worked_example(card: KnowledgeCard) -> None:
    """表示降级：用知识点具体例子替代抽象推导。"""
    example = card.example.strip()
    if not example:
        return
    st.markdown("**换成具体例子**")
    st.markdown(math_markdown(example))
    st.caption("先在这个例子上对齐概念，再回到原题。")


def _render_board_frame(frame: BoardFrameSpec) -> None:
    """渲染一帧分步板书；图形失败时保留文字说明。"""
    st.caption(f"板书 · 第 {frame.step_index} 步：{frame.title}")
    if frame.narration:
        st.markdown(math_markdown(frame.narration))
    if render_frame(frame) == "failed":
        st.info(f"{ICON_INFO} 这一步的图形暂不可用，已保留文字说明。")


def _render_kc_visual_hint(kc_id: str) -> None:
    """答错步骤时提供该 KC 的动态讲解；未登记或失败不阻断。"""
    kc = KC_BY_ID.get(kc_id)
    if kc is None or get_kc_visual(kc_id) is None:
        return
    with st.expander(f"动态讲解：{kc.name}", expanded=False):
        if render_kc_visual(kc_id) == "failed":
            st.info(f"{ICON_INFO} 动态讲解暂不可用，已保留文字讲解。")


@st.fragment
def _render_exercise_kc_visuals(exercise_id: str) -> None:
    """诊断页按题目关联的 KC 展示动态讲解。"""
    pairs = kc_visuals_for_exercises((exercise_id,))
    if not pairs:
        return
    st.markdown("**KC 动态讲解**")
    for kc_id, name in pairs:
        with st.expander(f"动态讲解：{name}", expanded=False):
            if render_kc_visual(kc_id) == "failed":
                st.info(
                    f"{ICON_INFO} 动态讲解暂不可用，已保留文字讲解。"
                )


def _load_step_insights(exercise_id: str):
    """读取本机步骤运行并聚合近期卡点；游客模式或读取失败为空。"""
    consent: Consent = st.session_state.consent
    if not (consent.memory or consent.mistake_book):
        return ()
    try:
        if not step_db_path().exists():
            return ()
        with StepStore() as store:
            runs = store.list_runs(limit=100)
    except (OSError, sqlite3.Error):
        return ()
    return build_step_insights(runs, exercise_id)


def _render_step_insight(engine: SessionEngine, key: str) -> None:
    """在步骤区展示自己的近期卡点，并提供到该步的追问锚点。"""
    insights = _load_step_insights(engine.current_exercise.id)
    if not insights:
        return
    top = insights[0]
    st.caption(
        f"近期卡点：最近 {top.run_count} 次里，"
        f"第 {top.step_index} 步错了 {top.fail_count} 次。"
    )
    if st.button(
        "针对这一步提问",
        key=f"{key}_insight_ask",
        icon=ICON_HINT,
    ):
        engine.request_hint("step", step_index=top.step_index)
        st.rerun()


@st.fragment
def _render_step_guide(engine: SessionEngine) -> None:
    """为有步骤元数据的题目渲染可选的分步填写区。

    片段化后检查单步只重跑本区域，不整页重建可视化与小测控件。
    """
    specs = STEP_SPECS.get(engine.current_exercise.id)
    if not specs:
        return
    key = _step_state_key(engine)
    if key not in st.session_state:
        st.session_state[key] = {
            "run_id": "",
            "attempts": {},
            "finalized": False,
        }
    state = st.session_state[key]
    frames = {
        frame.step_index: frame
        for frame in BOARD_FRAMES.get(engine.current_exercise.id, ())
    }
    with st.expander("分步填写（可选）", expanded=True):
        st.caption(
            "先逐步填写中间结果；最终答案仍以下方“提交答案”为准。"
        )
        _render_step_insight(engine, key)
        for spec in specs:
            attempt = state["attempts"].get(spec.index)
            frame = frames.get(spec.index)
            if attempt is not None:
                _render_step_result(spec, attempt)
                continue
            if frame is not None:
                _render_board_frame(frame)
            st.markdown(f"**第 {spec.index} 步**：{spec.prompt}")
            start_key = f"{key}_started_{spec.index}"
            if start_key not in st.session_state:
                st.session_state[start_key] = time.time()
            if frame is not None and st.button(
                "针对这一步提问",
                key=f"{key}_ask_{spec.index}",
                icon=ICON_HINT,
            ):
                engine.request_hint("step", step_index=spec.index)
                st.rerun()
            answer = st.text_input(
                "这一步的结果",
                key=f"{key}_input_{spec.index}",
            )
            if st.button(
                "检查这一步",
                key=f"{key}_check_{spec.index}",
                disabled=not answer.strip(),
            ):
                elapsed_s = max(
                    0.0,
                    time.time()
                    - float(st.session_state.pop(start_key, time.time())),
                )
                try:
                    recorder = _step_recorder()
                    try:
                        if not state["run_id"]:
                            state["run_id"] = recorder.start(
                                engine.current_exercise.id,
                                engine.card.id,
                                specs,
                            )
                        state["attempts"][spec.index] = (
                            recorder.record(
                                state["run_id"],
                                spec,
                                answer,
                                elapsed_s=elapsed_s,
                            )
                        )
                    finally:
                        recorder.close()
                except (OSError, sqlite3.Error):
                    st.warning("步骤记录暂不可用，请稍后再试。")
                else:
                    _invalidate_kc_mastery_cache()
                    rerun_fragment()
        if state["attempts"]:
            st.caption(
                f"已填写 {len(state['attempts'])} / {len(specs)} 步。"
            )
        if state["finalized"]:
            st.caption("最终答案已提交，步骤记录已结算。")


def _render_step_result(spec: StepSpec, attempt: StepAttempt) -> None:
    """把已判定步骤渲染成原位标注：输入、徽标与可展开原因。"""
    marker = present_verdict(attempt.verdict)
    with st.container(border=True):
        st.markdown(f"**第 {spec.index} 步**：{spec.prompt}")
        st.caption(f"你的输入：{attempt.input}")
        getattr(st, marker.tone)(STEP_VERDICT_LABELS[attempt.verdict])
        with st.expander("为什么这样判定？", expanded=False):
            st.markdown(build_step_reason(spec, attempt))
        if attempt.verdict is StepVerdict.INCORRECT:
            st.caption(
                "回到这一步对应的概念，再检查一次；"
                "最终答案仍以下方提交为准。"
            )
            _render_kc_visual_hint(spec.kc_id)


def _finalize_step_run(
    engine: SessionEngine, answer: str, correct: bool | None
) -> None:
    """把最终答案与正确性补写到本次步骤运行。"""
    key = _step_state_key(engine)
    state = st.session_state.get(key)
    if not state or not state.get("run_id") or state.get("finalized"):
        return
    recorder = _step_recorder()
    try:
        recorder.finalize(
            state["run_id"], final_answer=answer, final_correct=correct
        )
    except (OSError, sqlite3.Error):
        return
    finally:
        recorder.close()
    state["finalized"] = True
    _invalidate_kc_mastery_cache()


def _abandon_active_step_runs() -> None:
    """把未结算的步骤运行标记为放弃，并应用已有 KC 观测。"""
    changed = False
    for key in list(st.session_state.keys()):
        if not key.startswith("step_state_"):
            continue
        state = st.session_state.get(key)
        if not isinstance(state, dict):
            continue
        if state.get("finalized") or not state.get("run_id"):
            continue
        try:
            recorder = _step_recorder()
            try:
                recorder.abandon(state["run_id"])
            finally:
                recorder.close()
        except (OSError, sqlite3.Error):
            pass
        state["finalized"] = True
        changed = True
    if changed:
        _invalidate_kc_mastery_cache()


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
        st.session_state.engine = _build_session_engine(cards[0])
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


def _clear_similar_session() -> None:
    """清理同类/相似练习状态与召回信号映射。"""
    for key in (
        "similar_state",
        "similar_impressions",
        "similar_source_id",
        "similar_fallback_used",
        "similar_transfer_count",
    ):
        st.session_state.pop(key, None)


def _start_similar_recall(
    entry: MistakeEntry,
    repository: Repository,
    consent: Consent,
) -> bool:
    """按 KC、错因与题干结构发起相似题召回；为空时只提示不阻断。"""
    base = query_from_mistake(entry, cards)
    query = RecallQuery(
        exercise=base.exercise,
        card_id=base.card_id,
        error_type=base.error_type,
        completed_exercise_ids=frozenset(
            receipt.exercise_id
            for receipt in repository.list_receipts(limit=None)
        ),
    )
    result = recall_similar(query, cards, tree=_load_knowledge_tree())
    if not result.candidates:
        st.info(f"{ICON_INFO} 暂无可用相似题，可先复习本知识点。")
        return False
    questions = tuple(
        DailyQuestion(candidate.card, candidate.exercise)
        for candidate in result.candidates
    )
    impressions: dict[str, str] = {}
    if consent.mistake_book:
        with RecallStore() as store:
            impressions = store.record_impression(
                entry.exercise_id, list(result.candidates)
            )
    _clear_similar_session()
    st.session_state.similar_state = DailyState(
        date_key=f"recall-{time.time_ns()}",
        questions=questions,
        started_at=datetime.now(timezone.utc),
    )
    st.session_state.similar_impressions = impressions
    st.session_state.similar_source_id = entry.exercise_id
    st.session_state.similar_fallback_used = result.fallback_used
    st.session_state.similar_transfer_count = sum(
        1 for candidate in result.candidates if candidate.is_transfer
    )
    return True


def _render_mistake_book(
    repository: Repository, consent: Consent
) -> None:
    """渲染最近错题、逐题先修诊断与相似题入口。"""
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
        if st.button(
            "练相似题",
            key=f"recall_{entry.id}",
            icon=ICON_PLAY,
        ):
            if _start_similar_recall(entry, repository, consent):
                st.rerun()
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
        _abandon_active_step_runs()
        _clear_similar_session()
        with st.spinner("正在加载卡片…"):
            st.session_state.engine = _build_session_engine(selected_card)
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


def _render_independent_check(
    engine: SessionEngine, receipt: Receipt
) -> None:
    """依赖度较高时提供一道无提示同类题；结果不写入学习档案。"""
    signal = _cached_dependence_signal(engine.card.id)
    if signal.level is DependenceLevel.NONE:
        return
    key = f"independent_verify_{receipt.id}"
    done = st.session_state.get(key)
    if isinstance(done, dict):
        result = done.get("result")
        exercise = done.get("exercise")
        if result == "correct":
            st.success(f"{ICON_CHECK} 独立完成，这次没有使用提示。")
        elif result == "wrong":
            st.info(
                f"{ICON_INFO} 这次没做对，不记录成绩；可以回到原题继续。"
            )
        elif result == "unverified":
            st.caption("这一步无法自动核对，本次不计入结果。")
        else:
            st.caption("已跳过独立验证。")
        if isinstance(exercise, Exercise):
            with st.expander("查看这道题的解析", expanded=False):
                st.markdown(math_markdown(exercise.solution_outline))
        return
    repository = st.session_state.repository
    try:
        completed = frozenset(
            item.exercise_id
            for item in repository.list_receipts(limit=None)
        )
    except (OSError, sqlite3.Error):
        completed = frozenset()
    query = RecallQuery(
        exercise=engine.current_exercise,
        card_id=engine.card.id,
        completed_exercise_ids=completed,
    )
    try:
        result = recall_similar(
            query, cards, tree=_load_knowledge_tree(), limit=3
        )
    except Exception:
        return
    candidates = [
        item
        for item in result.candidates
        if item.exercise.id != engine.current_exercise.id
    ]
    if not candidates:
        return
    candidate = candidates[0]
    with st.container(border=True):
        st.markdown("**独立验证（可选）**")
        st.caption(
            "换一道同类题，不给提示；结果不计入收据与掌握度。"
        )
        st.write(math_markdown(candidate.exercise.stem))
        answer = _render_answer_input(
            candidate.exercise, key_suffix=f"verify_{receipt.id}"
        )
        first, second = st.columns(2)
        if first.button(
            "提交验证",
            key=f"verify_submit_{receipt.id}",
            disabled=not answer.strip(),
            **button_kwargs(PRIMARY),
        ):
            judgement = evaluate(candidate.exercise, answer)
            if judgement.correct is True:
                outcome = "correct"
            elif judgement.correct is False:
                outcome = "wrong"
            else:
                outcome = "unverified"
            st.session_state[key] = {
                "result": outcome,
                "exercise": candidate.exercise,
            }
            st.rerun()
        if second.button("跳过", key=f"verify_skip_{receipt.id}"):
            st.session_state[key] = {
                "result": "skipped",
                "exercise": candidate.exercise,
            }
            st.rerun()


def _render_path_probe(
    receipt: Receipt,
    path: SolutionPath,
    *,
    position: int,
    total: int,
) -> None:
    """渲染一条备选路径；检查点通过后才揭示路径名称与总结。"""
    key = f"path_probe_{receipt.id}_{path.path_id}"
    state = st.session_state.get(key)
    if not isinstance(state, dict):
        state = {"stage": 0, "done": False}
        st.session_state[key] = state
    if state.get("done"):
        st.success(f"路径成立：{path.name}")
        st.markdown(math_markdown(path.summary))
        if path.final_answer:
            st.caption(f"最终答案：{path.final_answer}")
        return
    stage = min(int(state.get("stage", 0)), len(path.checkpoints) - 1)
    checkpoint = path.checkpoints[stage]
    label = "另一种思路" if total == 1 else f"另一种思路 {position}/{total}"
    st.markdown(
        f"**{label} · 关键一步 {stage + 1} / {len(path.checkpoints)}**"
    )
    st.markdown(math_markdown(checkpoint.prompt))
    answer = st.text_input(
        "这一步的结果",
        key=f"{key}_input_{stage}",
    )
    if st.button(
        "验证这一步",
        key=f"{key}_submit_{stage}",
        disabled=not answer.strip(),
        **button_kwargs(PRIMARY),
    ):
        verdict = check_checkpoint(checkpoint, answer)
        if verdict is StepVerdict.CORRECT:
            state["stage"] = stage + 1
            if state["stage"] >= len(path.checkpoints):
                state["done"] = True
            st.rerun()
        elif verdict is StepVerdict.REJECTED:
            st.warning("输入格式不符合，请用数值或表达式。")
        elif verdict is StepVerdict.UNVERIFIABLE:
            st.info("无法自动核对，请检查写法后重试。")
        else:
            st.warning("这一步还不对，再检查一下。")


def _render_strategy_probe(receipt: Receipt) -> None:
    """收据后的多解入口；没有登记路径的题目不展示。"""
    paths = PATHS.get(receipt.exercise_id, ())
    if not paths:
        return
    with st.expander("还有没有别的方法？", expanded=False):
        st.caption(
            "先写出关键一步，验证通过后再显示这条思路；"
            "不影响本次收据与掌握度。"
        )
        for position, path in enumerate(paths, start=1):
            _render_path_probe(
                receipt, path, position=position, total=len(paths)
            )


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
            _invalidate_kc_mastery_cache()
            st.rerun()

        if not (consent.memory or consent.mistake_book):
            st.info(f"{ICON_INFO} 游客模式：本次学习数据只存在内存中。")
        st.divider()
        if st.button("重置会话", key="reset_session", icon=ICON_RESTART):
            _abandon_active_step_runs()
            _clear_similar_session()
            st.session_state.engine = _build_session_engine(
                st.session_state.engine.card
            )
            st.rerun()


def _render_mistake_tab() -> None:
    """渲染相似题练习或错题本的统计、错题与复习清单。"""
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    if not consent.mistake_book:
        st.subheader("错题本")
        st.info(f"{ICON_INFO} 错题本已关闭。")
        return
    if (
        st.session_state.get("similar_state") is not None
        and st.session_state.get("similar_source_id") is not None
    ):
        _render_similar_practice()
        return
    st.subheader("错题本")
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
    _render_mistake_book(repository, consent)
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


def _current_wrong_answers() -> list[str]:
    """收集当前题被判错的作答文本。"""
    exercise_id = engine.current_exercise.id
    return [
        attempt["answer"]
        for attempt in engine.state.attempts
        if attempt["exercise_id"] == exercise_id
        and attempt.get("correct") is False
    ]


def _render_attribution_feedback(*, show_evidence: bool = False) -> None:
    """渲染单次作答的只读归因；不改变判分、掌握度或复习安排。"""
    wrong_answers = _current_wrong_answers()
    if not wrong_answers:
        return
    exercise = engine.current_exercise
    online = current_settings(
        st.session_state.consent
    ).analysis_online_enabled
    signature = (
        exercise.id,
        len(engine.state.attempts),
        engine.state.max_hint_level,
        tuple(engine.state.hint_requests),
        online,
    )
    cache_key = "attribution_" + "_".join(
        str(item) for item in signature
    )
    report = st.session_state.get(cache_key)
    if report is None:
        diagnosis = diagnose(
            exercise, wrong_answers, tuple(engine.state.hint_requests)
        )
        if (
            engine.state.diagnosis is not None
            and engine.state.diagnosis != diagnosis.error_type
        ):
            diagnosis = Diagnosis(
                engine.state.diagnosis, "已按诊断阶段确认的错因"
            )
        started = engine.state.exercise_started_at
        duration_s = (
            int((datetime.now(timezone.utc) - started).total_seconds())
            if started is not None
            else None
        )
        attempt_count = sum(
            1
            for attempt in engine.state.attempts
            if attempt["exercise_id"] == exercise.id
        )
        attribution = build_attribution(
            exercise,
            wrong_answers,
            tuple(engine.state.hint_requests),
            max_hint_level=engine.state.max_hint_level,
            attempt_count=attempt_count,
            duration_s=duration_s,
            diagnosis=diagnosis,
        )
        narrator = build_narrator(enabled=online)
        with loading_skeleton(SKELETON_INLINE):
            report = narrator.narrate(attribution)
        st.session_state[cache_key] = report
    st.markdown("**错因归因（只读）**")
    st.markdown(
        f"- 类型：{report.error_type.value} · "
        f"置信度 {report.confidence:.0%}\n"
        f"- 可能原因：{report.underlying_cause}\n"
        f"- 下一步：{report.suggested_next_action.text}"
    )
    if show_evidence and report.evidence:
        with st.expander("归因依据"):
            for item in report.evidence:
                st.caption(item.text)
    if report.caveats:
        st.caption("；".join(report.caveats))
    if report.needs_verification:
        st.warning("涉及数学等价性的内容未自动确认，请自行核对。")
    source = "在线分析" if report.source == "llm" else "本地规则模板"
    st.caption(
        f"来源：{source}；归因只读，不影响判分、掌握度或复习安排。"
    )


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
        _clear_similar_session()
        st.session_state.similar_state = DailyState(
            date_key=f"similar-{time.time_ns()}",
            questions=similar_questions,
            started_at=datetime.now(timezone.utc),
        )
        st.rerun()


def _render_similar_practice() -> None:
    """诊断或错题本发起的小练习；答完可回到来源。"""
    state: DailyState | None = st.session_state.get("similar_state")
    if state is None:
        st.info(f"{ICON_INFO} 暂无同类练习，请先回到卡片诊断错因。")
        return
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    source_id = st.session_state.get("similar_source_id")
    source = repository.find_mistake(source_id) if source_id else None
    is_recall = source is not None
    if is_recall:
        source_card = next(
            (card for card in cards if card.id == source.card_id), None
        )
        card_name = (
            source_card.name if source_card is not None else source.card_id
        )
        transfer_count = st.session_state.get("similar_transfer_count", 0)
        st.subheader("相似题练习")
        st.caption(
            f"{card_name} · 共 {len(state.questions)} 题 · "
            f"结构迁移 {transfer_count} 道"
        )
        stem = source.stem
        st.caption(
            "召回自错题："
            + (stem if len(stem) <= 60 else f"{stem[:60]}…")
        )
        if st.session_state.get("similar_fallback_used"):
            st.info(f"{ICON_INFO} 相似题不足，已改用同知识点的未做题。")
    else:
        st.subheader("同类练习")
        st.caption(
            f"{engine.card.name} · 共 {len(state.questions)} 题，"
            "答完自动结算，不影响当前诊断。"
        )

    def _on_submission(
        submission: DailySubmission, answer: str, moment: datetime
    ) -> None:
        """登记做题结果；来自错题本的题目同时写召回效果信号。"""
        impressions: dict[str, str] = (
            st.session_state.get("similar_impressions") or {}
        )
        impression_id = impressions.get(submission.question.exercise.id)
        if impression_id is not None:
            with RecallStore() as store:
                store.record_outcome(impression_id, submission.correct)
        if submission.correct is True:
            _record_review_write(
                submission.question.exercise.id,
                True,
                submission.duration_s,
            )
        elif submission.correct is False:
            _record_review_write(
                submission.question.exercise.id,
                False,
                submission.duration_s,
            )
            record_daily_mistake(
                repository,
                consent,
                submission.question,
                answer,
                moment,
                duration_s=submission.duration_s,
            )

    _render_active_quiz(
        state,
        key_prefix="similar",
        on_submission=_on_submission,
        summary_title="相似题练习完成" if is_recall else "同类练习完成",
    )
    if state.finished and st.button(
        "返回错题本" if is_recall else "回到诊断",
        key="similar_back",
        icon=ICON_RESTART,
    ):
        _clear_similar_session()
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


@st.fragment
def _render_visual_block(card_id: str) -> None:
    """可视化片段：滑块交互只重跑图表，不重建整页。"""
    if render_visual(card_id) == "failed":
        st.info(f"{ICON_INFO} 可视化暂不可用")


def _render_scenario_block(card_id: str) -> None:
    """讲解页的情境探索入口；失败时只提示，不阻断小测。"""
    spec = SCENARIOS.get(card_id)
    if spec is None:
        return
    with st.expander(f"情境探索：{spec.title}", expanded=False):
        if render_scenario(spec) == "failed":
            st.info(f"{ICON_INFO} 情境组件暂不可用，已保留文字讲解。")
        if spec.bridge:
            st.caption(spec.bridge)


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
            _render_visual_block(engine.card.id)
            _render_scenario_block(engine.card.id)
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
            _render_hint_ceiling_banner(engine)
            _render_visual_block(engine.card.id)
            st.write(math_markdown(view.body))
            _render_step_guide(engine)
            with st.form(
                "quiz_answer_form",
                clear_on_submit=False,
                border=False,
            ):
                answer = _render_answer_input(engine.current_exercise)
                submitted = st.form_submit_button(
                    "提交答案",
                    key="submit_answer",
                    icon=ICON_SUBMIT,
                    **button_kwargs(PRIMARY),
                )
            if submitted:
                attempts_before = len(engine.state.attempts)
                next_view = engine.submit_answer(answer)
                if len(engine.state.attempts) > attempts_before:
                    _finalize_step_run(
                        engine,
                        answer,
                        engine.state.attempts[-1].get("correct"),
                    )
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
            _render_exercise_kc_visuals(engine.current_exercise.id)
            _render_attribution_feedback(show_evidence=True)
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
        if view.follow_up is not None:
            st.caption(f"当前题目：{engine.current_exercise.stem}")
            if view.follow_up.anchor_step_index is not None:
                st.caption(
                    f"当前步骤：第 {view.follow_up.anchor_step_index} 步"
                )
            hint_block(
                view.follow_up.level,
                math_markdown(view.follow_up.prompt),
            )
            stage = stage_for_level(view.follow_up.level)
            st.caption(f"REMSJ · {stage.label}：{stage.description}")
            if view.follow_up.supplement:
                st.caption("再补充一个更具体的问题。")
            if view.notice:
                st.caption(view.notice)
            voice_key = (
                f"voice_text_{engine.state.exercise_id}_"
                f"{len(engine.state.attempts)}_"
                f"L{view.follow_up.level}_"
                f"{int(view.follow_up.supplement)}"
            )
            if voice_available():
                st.caption("语音回答仅在本机转写，不会上传。")
                audio = st.audio_input(
                    "语音回答（可选）", key=f"{voice_key}_audio"
                )
                if audio is not None and st.button(
                    "转写语音",
                    key=f"{voice_key}_transcribe",
                    icon=ICON_HINT,
                ):
                    with st.spinner("正在本机转写…"):
                        spoken = transcribe_and_normalize(
                            audio.getvalue()
                        )
                    if spoken:
                        st.session_state[voice_key] = spoken
                    else:
                        st.warning("没有识别到内容，请改用文字输入。")
                spoken_text = st.session_state.get(voice_key)
                if spoken_text:
                    st.info(f"识别为：{spoken_text}")
                    if st.button(
                        "提交语音回答",
                        key=f"{voice_key}_submit",
                        icon=ICON_SUBMIT,
                        **button_kwargs(PRIMARY),
                    ):
                        engine.submit_follow_up(spoken_text)
                        st.rerun()
            answer = st.text_input(
                "你的回答",
                key=(
                    f"follow_up_{engine.state.exercise_id}_"
                    f"{len(engine.state.attempts)}_"
                    f"L{view.follow_up.level}_"
                    f"{int(view.follow_up.supplement)}"
                ),
            )
            if st.button(
                "提交追问回答",
                key="submit_follow_up",
                icon=ICON_SUBMIT,
                disabled=not answer.strip(),
                **button_kwargs(PRIMARY),
            ):
                engine.submit_follow_up(answer)
                st.rerun()
            return
        current_id = engine.state.exercise_id
        if any(
            attempt["exercise_id"] == current_id
            and attempt.get("correct") is False
            for attempt in engine.state.attempts
        ):
            st.error(f"{ICON_ERROR} 再看一眼提示")
        hint_block(engine.state.hint_level, math_markdown(view.body))
        stage = stage_for_level(engine.state.hint_level)
        st.caption(f"REMSJ · {stage.label}：{stage.description}")
        if view.notice:
            st.caption(view.notice)
        _render_hint_ceiling_banner(engine)
        if view.representation is Representation.WORKED_EXAMPLE:
            _render_worked_example(engine.card)
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
        _render_attribution_feedback()
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
            if receipt is not None:
                _render_dependence_note(engine.card.id)
                _render_independent_check(engine, receipt)
                _render_strategy_probe(receipt)
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
                _abandon_active_step_runs()
                st.session_state.engine = _build_session_engine(engine.card)
                st.rerun()
        return


KC_MASTERY_CACHE_KEY = "kc_mastery_snapshot"


def _invalidate_kc_mastery_cache() -> None:
    """步骤写入 KC 影子库后丢弃会话缓存。"""
    st.session_state.pop(KC_MASTERY_CACHE_KEY, None)


def _load_kc_mastery() -> tuple[dict[str, float], dict[str, int]]:
    """读取 KC 影子掌握度与样本量；会话内缓存，步骤写入后失效。"""
    cached = st.session_state.get(KC_MASTERY_CACHE_KEY)
    if cached is not None:
        return cached
    if not shadow_db_path().exists():
        result: tuple[dict[str, float], dict[str, int]] = ({}, {})
        st.session_state[KC_MASTERY_CACHE_KEY] = result
        return result
    try:
        with KCMasteryStore() as store:
            mastery, samples = store.load_with_samples()
    except (OSError, sqlite3.Error):
        return {}, {}
    result = (mastery, samples)
    st.session_state[KC_MASTERY_CACHE_KEY] = result
    return result


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
    *,
    kc_mastery: dict[str, float] | None = None,
    kc_samples: dict[str, int] | None = None,
    repair_plan: RepairPlan | None = None,
) -> list[Recommendation]:
    """按前置修复、先修复拓扑顺序、KC 影子与 BKT 推荐 3 张卡片。"""
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
    kc_recommendations = weak_kc_recommendations(
        cards,
        kc_mastery,
        sample_sizes=kc_samples,
        card_mastery=mastery,
    )
    repair_recommendations: list[Recommendation] = []
    seen_repair_cards: set[str] = set()
    for item in (
        repair_plan.items if repair_plan is not None else ()
    ):
        card_id = item.prerequisite_card_id
        if not card_id or card_id in seen_repair_cards:
            continue
        seen_repair_cards.add(card_id)
        repair_recommendations.append(
            Recommendation(
                card_id=card_id,
                reason=f"先修补齐：{item.prerequisite_name}",
                basis=item.reason,
            )
        )
    base = recommend(
        [card.id for card in cards],
        prerequisites,
        mastered,
        weak_cards,
        limit=3,
        mastery=mastery,
    )
    merged: list[Recommendation] = []
    seen: set[str] = set()
    for recommendation in (
        *repair_recommendations,
        *kc_recommendations,
        *base,
    ):
        if recommendation.card_id in seen:
            continue
        seen.add(recommendation.card_id)
        merged.append(recommendation)
        if len(merged) >= 3:
            break
    return merged


def _start_card_session(card_id: str) -> None:
    """切换到指定卡片并回到陪练页。"""
    selected_card = next(card for card in cards if card.id == card_id)
    _abandon_active_step_runs()
    _clear_similar_session()
    st.session_state.engine = _build_session_engine(selected_card)
    st.session_state["card_selector"] = selected_card.id
    st.session_state["app_mode"] = MODE_SESSION
    st.session_state["main_tabs"] = "当前任务"


def _render_dashboard() -> None:
    """渲染学习仪表盘与下一步推荐。"""
    render_dynamic_background(st.session_state.consent)
    repository = RepositorySnapshot(st.session_state.repository)
    summary = build_dashboard(repository, datetime.now(timezone.utc))
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
    mastery_rows = _mastery_rows(repository)
    if mastery_rows:
        st.markdown("**掌握概率**")
        for card_id, text in mastery_rows:
            st.markdown(f"- {card_id}")
            st.caption(f"依据：{text}")
    kc_mastery, kc_samples = _load_kc_mastery()
    kc_progress = build_kc_progress(
        cards, kc_mastery, sample_sizes=kc_samples
    )
    if kc_progress:
        st.markdown("**KC 掌握度（步骤级影子）**")
        for item in kc_progress:
            st.markdown(
                f"- {item.name}：{item.probability:.0%}"
                f"（样本 {item.sample_size}）"
            )
    repair_plan = build_repair_plan(
        cards,
        kc_mastery,
        sample_sizes=kc_samples,
        mistakes=repository.list_mistakes(limit=None),
    )
    if repair_plan.items:
        st.markdown("**前置修复建议**")
        card_names = {card.id: card.name for card in cards}
        for item in repair_plan.items:
            st.markdown(f"- {item.reason}")
            if item.prerequisite_card_id:
                st.button(
                    "先修补先修："
                    f"{card_names.get(item.prerequisite_card_id, item.prerequisite_card_id)}",
                    key=(
                        f"repair_{item.prerequisite_kc_id}_"
                        f"{item.dependent_kc_id}"
                    ),
                    icon=ICON_PLAY,
                    on_click=_start_card_session,
                    args=(item.prerequisite_card_id,),
                )
        for note in repair_plan.notes:
            st.caption(note)
    recommendations = _next_recommendations(
        repository,
        cards,
        prerequisites,
        kc_mastery=kc_mastery,
        kc_samples=kc_samples,
        repair_plan=repair_plan,
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
        progress = _narrative_progress(repository)
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


def _quiz_wrong_key(key: str) -> str:
    """返回某次限时小测的错题登记键。"""
    return f"quiz_wrong:{key}"


def _record_quiz_wrong(
    key: str, position: int, question: DailyQuestion, answer: str
) -> None:
    """登记结算页要展示的错题；只存当前会话。"""
    session_key = _quiz_wrong_key(key)
    bucket = st.session_state.get(session_key)
    if bucket is None:
        bucket = []
        st.session_state[session_key] = bucket
    bucket.append((position, question, answer))


def _render_quiz_attributions(key: str) -> None:
    """结算页展示错题的只读归因；没有错题时不显示。"""
    wrong = st.session_state.get(_quiz_wrong_key(key))
    if not wrong:
        return
    online = current_settings(
        st.session_state.consent
    ).analysis_online_enabled
    report_key = f"quiz_reports:{key}:{online}"
    reports = st.session_state.get(report_key)
    if reports is None:
        narrator = build_narrator(enabled=online)
        reports = []
        for position, question, answer in wrong:
            report = narrator.narrate(
                build_attribution(question.exercise, [answer])
            )
            reports.append((position, question, report))
            if report.source == "template":
                # 在线路径失败时不再逐题重试，避免结算页反复等待
                narrator = TemplateNarrator()
        st.session_state[report_key] = reports
    st.markdown("**错因归因（只读）**")
    for position, question, report in reports:
        st.markdown(
            f"- 第 {position} 题 · {question.card.name}："
            f"{report.error_type.value}（置信度 {report.confidence:.0%}）"
        )
        st.caption(
            f"可能原因：{report.underlying_cause}；"
            f"下一步：{report.suggested_next_action.text}"
        )
    if any(report.needs_verification for _, _, report in reports):
        st.warning("涉及数学等价性的内容未自动确认，请自行核对。")
    caveats = sorted(
        {
            caveat
            for _, _, report in reports
            for caveat in report.caveats
        }
    )
    if caveats:
        st.caption("；".join(caveats))
    source = (
        "在线分析"
        if any(report.source == "llm" for _, _, report in reports)
        else "本地规则模板"
    )
    st.caption(
        f"来源：{source}；归因只读，不影响判分、掌握度或复习安排。"
    )


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
    attribution_key: str | None = None,
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
        if attribution_key is not None:
            _render_quiz_attributions(attribution_key)
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
        position = state.index + 1
        submission = submit_daily_answer(state, answer, now)
        if submission is not None:
            if on_submission is not None:
                on_submission(submission, answer, now)
            if (
                attribution_key is not None
                and submission.correct is False
            ):
                _record_quiz_wrong(
                    attribution_key, position, submission.question, answer
                )
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
                repository,
                consent,
                submission.question,
                answer,
                moment,
                duration_s=submission.duration_s,
            )

    def _on_finish(finished_state: DailyState, moment: datetime) -> None:
        """保存每日挑战结果。"""
        save_daily_result(repository, consent, finished_state, moment)

    _render_active_quiz(
        state,
        key_prefix=f"daily_{day_key}",
        on_submission=_on_submission,
        on_finish=_on_finish,
        attribution_key=state.date_key,
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
                repository,
                consent,
                submission.question,
                answer,
                moment,
                duration_s=submission.duration_s,
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
        attribution_key=state.date_key,
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

    kc_mastery, kc_samples = _load_kc_mastery()
    kc_progress = build_kc_progress(
        cards, kc_mastery, sample_sizes=kc_samples, limit=5
    )
    if kc_progress:
        card_names = {card.id: card.name for card in cards}
        st.markdown("**KC 掌握度（步骤级影子）**")
        for item in kc_progress:
            marker = (
                " · 待补强"
                if item.probability < WEAK_KC_THRESHOLD
                else ""
            )
            st.markdown(
                f"- {item.name}：{item.probability:.0%}"
                f"（样本 {item.sample_size}）{marker}"
            )
            if item.card_ids:
                related = "、".join(
                    card_names.get(card_id, card_id)
                    for card_id in item.card_ids
                )
                st.caption(f"对应卡片：{related}")
        kc_recommendations = weak_kc_recommendations(
            cards,
            kc_mastery,
            sample_sizes=kc_samples,
            limit=1,
        )
        if kc_recommendations:
            recommendation = kc_recommendations[0]
            if (
                path.recommended_card is None
                or recommendation.card_id != path.recommended_card.id
            ):
                st.caption(
                    f"KC 视角：{recommendation.reason}；"
                    f"依据：{recommendation.basis}"
                )

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


WEEKLY_NARRATIVE_KEY = "weekly_report_narrative"


def _report_signature(report: ExplainableReport) -> tuple[object, ...]:
    """用结论与指标生成叙事缓存键；忽略生成时间。"""
    return tuple(
        (
            conclusion.id,
            conclusion.statement,
            tuple(
                (metric.id, metric.value)
                for metric in conclusion.metrics
            ),
        )
        for conclusion in report.conclusions
    )


def _render_weekly_report() -> None:
    """渲染最近 7 天的周报与错因趋势；AI 叙事按需生成。"""
    now = datetime.now(timezone.utc)
    repository = RepositorySnapshot(st.session_state.repository)
    report = build_weekly_report(repository, now)
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
    kc_mastery, _ = _load_kc_mastery()
    explainable = build_explainable_report(
        repository,
        now=now,
        kc_mastery=kc_mastery,
    )
    signature = _report_signature(explainable)
    client = build_report_client(st.session_state.provider)
    narrative = None
    if client is not None:
        if st.button(
            "生成 / 刷新 AI 叙事",
            key="weekly_narrative",
            icon=ICON_UPDATE,
        ):
            with loading_skeleton(SKELETON_PANEL):
                generated, reason = generate_report_narrative(
                    explainable, client=client
                )
            st.session_state[WEEKLY_NARRATIVE_KEY] = (
                signature,
                generated,
                reason,
            )
        cached = st.session_state.get(WEEKLY_NARRATIVE_KEY)
        if cached is not None and cached[0] == signature:
            narrative = cached[1]
            if narrative is None:
                st.caption(
                    f"AI 叙事暂不可用（{cached[2]}），已保留确定性报告。"
                )
    if narrative is not None:
        st.markdown(render_narrative_markdown(explainable, narrative))
        st.caption("叙事由模型改写；结论与证据来自统计层。")
    else:
        st.markdown(render_report_markdown(explainable))
        if client is None:
            st.caption("配置 AI 后可生成叙事；当前展示确定性报告。")


def _record_review_write(
    exercise_id: str,
    independent: bool,
    duration_s: int | None = None,
) -> None:
    """校验写入门后记录一次复习结果；弱正确按 HINTED 处理。"""
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
    review_quality = quality
    speed_weight = 1.0
    if independent and duration_s is not None:
        entry = repository.find_mistake(exercise_id)
        if entry is not None:
            reference = reference_seconds_from_history(
                repository.list_receipts(limit=None), entry.card_id
            )
            speed_weight = observation_weight(duration_s, reference)
            review_quality = quality_for_correct(duration_s, reference)
    updated = repository.record_review(
        exercise_id, independent=review_quality, now=now
    )
    if updated is not None:
        repository.record_mastery(
            updated.card_id,
            correct=independent,
            now=now,
            quality=quality,
            mastery_weight=speed_weight,
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
            kc_mastery, kc_samples = _load_kc_mastery()
            repair_plan = build_repair_plan(
                cards,
                kc_mastery,
                sample_sizes=kc_samples,
                mistakes=repository.list_mistakes(limit=None),
            )
            priority |= {
                item.prerequisite_card_id
                for item in repair_plan.items
                if item.prerequisite_card_id
            }
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
            _record_review_write(
                submission.question.exercise.id,
                True,
                submission.duration_s,
            )
        elif submission.correct is False:
            _record_review_write(
                submission.question.exercise.id,
                False,
                submission.duration_s,
            )
            record_daily_mistake(
                repository,
                consent,
                submission.question,
                answer,
                moment,
                duration_s=submission.duration_s,
            )

    _render_active_quiz(
        state,
        key_prefix="review",
        on_submission=_on_submission,
        summary_title="复习包完成",
        attribution_key=state.date_key,
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


def _render_worksheet() -> None:
    """渲染可打印练习单：只读生成 HTML/Markdown 下载。"""
    st.subheader("可打印练习单")
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    sources: dict[str, WorksheetSource] = {
        "当前卡片": WorksheetSource.CURRENT_CARD,
        "同章节/同课程多卡": WorksheetSource.SAME_TOPIC,
    }
    if consent.mistake_book:
        sources["待复习错题"] = WorksheetSource.DUE_REVIEW
        sources["错题本"] = WorksheetSource.MISTAKES
    options = list(sources)
    if st.session_state.get("worksheet_source") not in options:
        st.session_state["worksheet_source"] = options[0]
    source_label = st.radio(
        "题目来源",
        options,
        horizontal=True,
        key="worksheet_source",
    )
    count = st.selectbox(
        "题目上限",
        [5, 10, 15],
        index=1,
        key="worksheet_count",
    )
    include_answers = st.checkbox(
        "附答案页", value=True, key="worksheet_answers"
    )
    include_solutions = st.checkbox(
        "答案页附解题思路",
        value=False,
        key="worksheet_solutions",
        disabled=not include_answers,
    )
    now = datetime.now(timezone.utc)
    worksheet = build_worksheet(
        cards,
        source=sources[source_label],
        repository=repository,
        current_card_id=engine.card.id,
        count=count,
        include_answers=include_answers,
        include_solutions=include_solutions and include_answers,
        now=now,
    )
    st.markdown(
        f"**生成摘要**：{worksheet.source_label} · 共 {worksheet.count} 题"
    )
    for note in worksheet.notes:
        st.info(f"{ICON_INFO} {note}")
    if not worksheet.items:
        return
    preview = render_worksheet_markdown(worksheet)
    with st.expander("预览题目", expanded=True):
        st.markdown(preview)
    day = now.astimezone().strftime("%Y%m%d")
    left, right = st.columns(2)
    left.download_button(
        "下载可打印 HTML",
        data=render_worksheet_html(worksheet).encode("utf-8"),
        file_name=f"mathcoach-worksheet-{day}.html",
        mime="text/html",
        icon=ICON_EXPORT,
        key="worksheet_download_html",
    )
    right.download_button(
        "下载 Markdown",
        data=preview.encode("utf-8"),
        file_name=f"mathcoach-worksheet-{day}.md",
        mime="text/markdown",
        icon=ICON_EXPORT,
        key="worksheet_download_markdown",
    )
    st.caption(
        "只读生成，不修改掌握度、错题或复习进度；"
        "HTML 可直接用浏览器打印为 PDF。"
    )


def _render_planner() -> None:
    """渲染智能练习册：薄弱 KC、到期复习与迁移题配额。"""
    st.subheader("智能练习册")
    repository = st.session_state.repository
    consent: Consent = st.session_state.consent
    if not (consent.memory or consent.mistake_book):
        st.info(
            f"{ICON_INFO} 开启本机记忆或错题本后可生成个性化练习册。"
        )
        return
    count = st.selectbox(
        "题目上限",
        [5, 10, 15],
        index=1,
        key="planner_count",
    )
    now = datetime.now(timezone.utc)
    kc_mastery, _ = _load_kc_mastery()
    with loading_skeleton(SKELETON_CARD):
        plan = build_worksheet_plan(
            cards,
            repository=repository,
            limit=count,
            current_card_id=engine.card.id,
            kc_mastery=kc_mastery,
            now=now,
        )
    if not plan.items:
        st.info(f"{ICON_INFO} 暂无可生成的题目。")
        return
    columns = st.columns(4)
    columns[0].metric("题目", plan.count)
    columns[1].metric("迁移题", plan.transfer_count)
    columns[2].metric("到期题", plan.due_count)
    columns[3].metric("薄弱 KC", len(plan.weak_kcs))
    for note in plan.notes:
        st.caption(note)

    with st.expander("选题理由", expanded=True):
        for index, item in enumerate(plan.items, start=1):
            st.markdown(
                f"{index}. **{item.card.name}** · "
                f"{item.exercise.stem[:40]}  \n"
                f"   {item.reason_text}"
            )

    worksheet = plan_to_worksheet(plan)
    preview = render_plan_markdown(plan)
    with st.expander("预览练习册", expanded=False):
        st.markdown(preview)
    day = now.astimezone().strftime("%Y%m%d")
    left, right = st.columns(2)
    left.download_button(
        "下载可打印 HTML",
        data=render_worksheet_html(worksheet).encode("utf-8"),
        file_name=f"mathcoach-plan-{day}.html",
        mime="text/html",
        icon=ICON_EXPORT,
        key="planner_download_html",
    )
    right.download_button(
        "下载 Markdown",
        data=preview.encode("utf-8"),
        file_name=f"mathcoach-plan-{day}.md",
        mime="text/markdown",
        icon=ICON_EXPORT,
        key="planner_download_markdown",
    )
    st.caption(
        "只读生成，不修改掌握度、错题或复习进度；"
        "选题理由随 Markdown 一起导出。"
    )


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
        and st.session_state.get("similar_source_id") is None
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
    elif mode == MODE_WORKSHEET:
        _render_worksheet()
    elif mode == MODE_PLANNER:
        _render_planner()
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
