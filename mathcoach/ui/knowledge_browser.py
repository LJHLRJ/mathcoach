"""知识点浏览：层级树、学习卡片与“开始练习”。"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from ..config import db_path
from ..domain.knowledge_tree import (
    KnowledgeNode,
    KnowledgeTree,
    KnowledgeTreeError,
    load_knowledge_tree,
    load_learning_card,
)
from ..domain.models import Consent, KnowledgeCard, ReviewState
from ..llm import Provider
from ..memory.repository import Repository
from ..memory.settings_repo import SQLiteSettingsStore
from ..session.engine import SessionEngine
from .components import PRIMARY, button_kwargs
from .icons import ICON_PLAY

LEARNING_CARDS_ENABLED_KEY = "learning_cards_enabled"
READY_THRESHOLD = 0.6


@dataclass(frozen=True)
class LearningStatus:
    """知识点的学习闭环状态。

    Attributes:
        state: 未开始 / 学习中 / 待复习 / 已熟练。
        mastery: BKT 掌握概率，没有记录时为 None。
        receipt_count: 收据数。
        mistake_count: 错题数。
        pending_review: 未掌握的错题数。
        suggestion: 下一步建议。
    """

    state: str
    mastery: float | None
    receipt_count: int
    mistake_count: int
    pending_review: int
    suggestion: str


def summarize_learning(
    *,
    mastery: float | None,
    receipt_count: int,
    mistake_count: int,
    pending_review: int,
    prerequisites: tuple[str, ...] = (),
    ready_threshold: float = READY_THRESHOLD,
) -> LearningStatus:
    """把练习与掌握度汇总成闭环状态；只做展示，不参与调度。"""
    if pending_review > 0:
        state = "待复习"
        suggestion = (
            f"先复习 {pending_review} 道待复习错题，再继续本知识点。"
        )
    elif receipt_count == 0 and mistake_count == 0:
        state = "未开始"
        suggestion = "先看学习卡片，再点“开始练习此知识点”。"
        if prerequisites:
            suggestion += f"若卡住，先复习「{prerequisites[0]}」。"
    elif mastery is not None and mastery >= ready_threshold:
        state = "已熟练"
        suggestion = "可以继续下一个知识点，或回到学习路径查看推荐。"
    else:
        state = "学习中"
        if (
            mastery is not None
            and mastery < 0.3
            and prerequisites
        ):
            suggestion = (
                f"建议先复习「{prerequisites[0]}」，再继续本知识点。"
            )
        else:
            suggestion = "继续练习本知识点，必要时回看学习卡片。"
    return LearningStatus(
        state=state,
        mastery=mastery,
        receipt_count=receipt_count,
        mistake_count=mistake_count,
        pending_review=pending_review,
        suggestion=suggestion,
    )


def learning_status_for(
    repository: Repository, card_id: str, tree: KnowledgeTree
) -> LearningStatus:
    """汇总指定知识点的收据、错题、待复习与先修，生成闭环状态。"""
    receipts = [
        receipt
        for receipt in repository.list_receipts(limit=None)
        if receipt.card_id == card_id
    ]
    mistakes = [
        mistake
        for mistake in repository.list_mistakes(limit=None)
        if mistake.card_id == card_id
    ]
    pending = sum(
        1
        for mistake in mistakes
        if mistake.review_state is not ReviewState.MASTERED
    )
    prerequisites = tuple(
        node.name
        for node_id in tree.prerequisite_chain(card_id, max_depth=2)
        if (node := tree.node(node_id)) is not None
    )
    return summarize_learning(
        mastery=repository.get_mastery(card_id),
        receipt_count=len(receipts),
        mistake_count=len(mistakes),
        pending_review=pending,
        prerequisites=prerequisites,
    )


def render_learning_status(status: LearningStatus) -> None:
    """在知识点页与练习结束页复用同一闭环摘要。"""
    st.markdown("**学习闭环**")
    if status.mastery is None:
        st.caption(f"掌握度：暂无记录 · {status.state}")
    else:
        st.progress(status.mastery)
        st.caption(f"掌握度：{status.mastery:.0%} · {status.state}")
    st.caption(
        f"练习记录：{status.receipt_count} 张收据 · "
        f"{status.mistake_count} 道错题 · "
        f"{status.pending_review} 道待复习"
    )
    st.caption(f"下一步：{status.suggestion}")


def _is_guest(consent: Consent) -> bool:
    """记忆与错题本都关闭时视为游客。"""
    return not (consent.memory or consent.mistake_book)


def load_learning_cards_enabled(
    consent: Consent, path: Path | None = None
) -> bool:
    """读取“学习卡片显示”开关；默认开启。"""
    if _is_guest(consent):
        return bool(st.session_state.get(LEARNING_CARDS_ENABLED_KEY, True))
    if path is None:
        cached = st.session_state.get(LEARNING_CARDS_ENABLED_KEY)
        if isinstance(cached, bool):
            return cached
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            values = store.get_all()
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return True
    value = bool(values.get(LEARNING_CARDS_ENABLED_KEY, True))
    if path is None:
        st.session_state[LEARNING_CARDS_ENABLED_KEY] = value
    return value


def save_learning_cards_enabled(
    consent: Consent, enabled: bool, path: Path | None = None
) -> bool:
    """保存“学习卡片显示”开关；失败时不阻断主流程。"""
    if _is_guest(consent):
        st.session_state[LEARNING_CARDS_ENABLED_KEY] = bool(enabled)
        return True
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            store.set_many({LEARNING_CARDS_ENABLED_KEY: bool(enabled)})
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    st.session_state[LEARNING_CARDS_ENABLED_KEY] = bool(enabled)
    return True


def _first_card(
    tree: KnowledgeTree, cards_by_id: dict[str, KnowledgeCard]
) -> KnowledgeNode | None:
    """按学段、课程、知识点的顺序找第一张有卡的节点。"""
    for stage in tree.nodes.values():
        if stage.parent_id is not None:
            continue
        for course in tree.children(stage.id):
            for node in tree.children(course.id):
                if node.id in cards_by_id:
                    return node
    return None


def _resolve_focus(
    tree: KnowledgeTree,
    cards_by_id: dict[str, KnowledgeCard],
    focus_id: str | None,
) -> KnowledgeNode | None:
    """解析聚焦节点；无效或没有对应卡片时回退到第一张有卡的节点。"""
    focus = tree.node(focus_id) if focus_id else None
    if focus is not None:
        if focus.id in cards_by_id:
            return focus
        for course in tree.children(focus.id):
            for node in tree.children(course.id):
                if node.id in cards_by_id:
                    return node
        for node in tree.children(focus.id):
            if node.id in cards_by_id:
                return node
    return _first_card(tree, cards_by_id)


def _strip_leading_title(text: str) -> str:
    """去掉学习卡片正文开头的 Markdown 一级标题。"""
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _select_node(node_id: str) -> None:
    """把知识点写进查询参数并触发重跑。"""
    st.query_params["kp"] = node_id
    st.rerun()


def _render_tree(
    tree: KnowledgeTree,
    cards_by_id: dict[str, KnowledgeCard],
    current: KnowledgeNode,
    stage_id: str | None,
) -> None:
    """渲染学段、课程、知识点三级树，当前节点用标记代替按钮。"""
    for stage in tree.nodes.values():
        if stage.parent_id is not None:
            continue
        with st.expander(stage.name, expanded=stage.id == stage_id):
            for course in tree.children(stage.id):
                st.markdown(f"**{course.name}**")
                for node in tree.children(course.id):
                    if node.id not in cards_by_id:
                        continue
                    if node.id == current.id:
                        st.caption(f"● {node.name}")
                    elif st.button(
                        node.name,
                        key=f"knowledge_node_{node.id}",
                    ):
                        _select_node(node.id)


def render_knowledge_browser(
    cards: list[KnowledgeCard],
    provider: Provider,
    repository: Repository,
    consent: Consent,
    focus_id: str | None = None,
) -> None:
    """渲染知识点层级、学习卡片与练习入口。"""
    st.subheader("知识点浏览")
    try:
        tree = load_knowledge_tree()
    except KnowledgeTreeError as exc:
        st.error(f"知识点树加载失败：{exc}")
        return

    cards_by_id = {card.id: card for card in cards}
    focus = focus_id or st.query_params.get("kp")
    if isinstance(focus, list):
        focus = focus[0] if focus else None
    node = _resolve_focus(tree, cards_by_id, focus)
    if node is None:
        st.info("当前内容还没有可浏览的知识点。")
        return

    course = tree.node(node.parent_id) if node.parent_id else None
    stage = (
        tree.node(course.parent_id)
        if course is not None and course.parent_id
        else None
    )

    left, right = st.columns([1, 1.6])
    with left:
        _render_tree(tree, cards_by_id, node, stage.id if stage else None)
    with right:
        st.markdown(f"### {node.name}")
        card = cards_by_id.get(node.id)
        if card is not None:
            st.caption(f"{card.course} · {card.chapter}")
            st.markdown("**前置知识点**")
            if node.prerequisites:
                for parent_id in node.prerequisites:
                    parent = tree.node(parent_id)
                    if parent is not None and st.button(
                        parent.name,
                        key=f"knowledge_prereq_{parent.id}",
                    ):
                        _select_node(parent.id)
            else:
                st.caption("无")

        if not load_learning_cards_enabled(consent):
            st.info("学习卡片显示已关闭；可在“设置 → 外观”中开启。")
        else:
            text = load_learning_card(node.id)
            if text:
                st.markdown(_strip_leading_title(text))
            else:
                st.info("该知识点的学习卡片尚未填充。")

        if card is not None:
            render_learning_status(
                learning_status_for(repository, card.id, tree)
            )

        if card is not None and st.button(
            "开始练习此知识点",
            key="knowledge_start_practice",
            icon=ICON_PLAY,
            **button_kwargs(PRIMARY),
        ):
            st.session_state.engine = SessionEngine(
                card=card,
                provider=provider,
                repository=repository,
                consent=consent,
            )
            st.query_params.clear()
            st.rerun()
        if st.button("返回当前任务", key="knowledge_back"):
            st.query_params.clear()
            st.rerun()
