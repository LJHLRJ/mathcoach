"""按年级浏览卡片：筛选式切换，不隔离学习数据。"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from ..config import db_path
from ..domain.grade_index import (
    DIFFICULTY_VALUES,
    GRADE_VALUES,
    UNCLASSIFIED,
    GradeIndex,
)
from ..domain.models import Consent, KnowledgeCard
from ..memory.repository import Repository
from ..memory.settings_repo import SQLiteSettingsStore
from ..timeutil import end_of_local_day

DEFAULT_GRADE_KEY = "default_grade"

GRADE_LABELS = {
    "all": "全部年级",
    "mixed": "mixed · 混合",
    "unclassified": "未分类",
}
for _index in range(1, 13):
    GRADE_LABELS[f"g{_index}"] = f"g{_index} · {_index} 年级"
for _index in range(1, 5):
    GRADE_LABELS[f"u{_index}"] = f"u{_index} · 本科 {_index} 年级"
for _index in range(1, 4):
    GRADE_LABELS[f"m{_index}"] = f"m{_index} · 研究生 {_index} 年级"

DIFFICULTY_LABELS = {
    "all": "全部难度",
    "basic": "基础",
    "intermediate": "进阶",
    "advanced": "高级",
    "challenge": "挑战",
    "unclassified": "未分类",
}
GRADE_OPTIONS = ("all",) + GRADE_VALUES + (UNCLASSIFIED,)
DIFFICULTY_OPTIONS = ("all",) + DIFFICULTY_VALUES + (UNCLASSIFIED,)
STAGE_ORDER = {"highschool": 0, "undergraduate": 1, "graduate": 2}


def grade_label(value: str) -> str:
    """年级代码转展示文案。"""
    return GRADE_LABELS.get(value, value)


def _difficulty_label(value: str) -> str:
    """难度代码转展示文案。"""
    return DIFFICULTY_LABELS.get(value, value)


def _is_guest(consent: Consent) -> bool:
    """记忆与错题本都关闭时视为游客。"""
    return not (consent.memory or consent.mistake_book)


def load_default_grade(
    consent: Consent, path: Path | None = None
) -> str:
    """读取“默认进入年级”；默认全部年级。"""
    if _is_guest(consent):
        value = st.session_state.get(DEFAULT_GRADE_KEY, "all")
        return value if value in GRADE_OPTIONS else "all"
    if path is None:
        cached = st.session_state.get(DEFAULT_GRADE_KEY)
        if isinstance(cached, str) and cached in GRADE_OPTIONS:
            return cached
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            values = store.get_all()
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return "all"
    value = values.get(DEFAULT_GRADE_KEY, "all")
    if not isinstance(value, str) or value not in GRADE_OPTIONS:
        value = "all"
    if path is None:
        st.session_state[DEFAULT_GRADE_KEY] = value
    return value


def save_default_grade(
    consent: Consent, grade: str, path: Path | None = None
) -> bool:
    """保存“默认进入年级”；失败时不阻断主流程。"""
    if grade not in GRADE_OPTIONS:
        return False
    if _is_guest(consent):
        st.session_state[DEFAULT_GRADE_KEY] = grade
        return True
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            store.set_many({DEFAULT_GRADE_KEY: grade})
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    st.session_state[DEFAULT_GRADE_KEY] = grade
    return True


def _card_metadata(
    index: GradeIndex,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """按卡汇总题目出现过的年级与难度集合。"""
    grades: dict[str, set[str]] = defaultdict(set)
    difficulties: dict[str, set[str]] = defaultdict(set)
    for record in index.records.values():
        grades[record.card_id].add(record.grade)
        difficulties[record.card_id].add(record.difficulty)
    return grades, difficulties


def _sort_key(card: KnowledgeCard) -> tuple[int, str, str]:
    """按学段、课程、名称排序。"""
    return (
        STAGE_ORDER.get(card.stage.value, 9),
        card.course,
        card.name,
    )


def _filtered_cards(
    cards: list[KnowledgeCard],
    index: GradeIndex,
    grade: str,
    difficulty: str,
) -> list[KnowledgeCard]:
    """按年级与难度筛选卡片，返回排序后的列表。"""
    grades, difficulties = _card_metadata(index)
    result: list[KnowledgeCard] = []
    for card in cards:
        if grade != "all" and grade not in grades.get(card.id, set()):
            continue
        if (
            difficulty != "all"
            and difficulty not in difficulties.get(card.id, set())
        ):
            continue
        result.append(card)
    return sorted(result, key=_sort_key)


def _grouped_cards(
    cards: list[KnowledgeCard], index: GradeIndex
) -> dict[str, list[KnowledgeCard]]:
    """按难度分组；没有难度的卡归入未分类。"""
    _, difficulties = _card_metadata(index)
    groups: dict[str, list[KnowledgeCard]] = {
        value: [] for value in DIFFICULTY_VALUES + (UNCLASSIFIED,)
    }
    for card in cards:
        values = difficulties.get(card.id) or {UNCLASSIFIED}
        for value in values:
            groups.setdefault(value, []).append(card)
    return groups


def _knowledge_cards_for_grade(
    cards: list[KnowledgeCard],
    spans: Mapping[str, tuple[str, ...]],
    grade: str,
) -> list[KnowledgeCard]:
    """取 grade_span 包含指定年级的卡；``all`` 返回全部。"""
    if grade == "all":
        return list(cards)
    return [
        card
        for card in cards
        if grade in spans.get(card.id, (UNCLASSIFIED,))
    ]


def _render_learning_entry(
    cards: list[KnowledgeCard],
    spans: Mapping[str, tuple[str, ...]],
    grade: str,
) -> None:
    """渲染“先学习本年级知识点”入口。"""
    with st.expander("先学习本年级知识点"):
        knowledge_cards = _knowledge_cards_for_grade(
            cards, spans, grade
        )
        if not knowledge_cards:
            st.caption("该年级暂无已标注知识点。")
            return
        ordered = sorted(knowledge_cards, key=_sort_key)
        labels = {
            card.id: f"{card.name} · {card.course}" for card in ordered
        }
        selected = st.selectbox(
            "选择知识点",
            list(labels),
            format_func=lambda value: labels[value],
            key=f"grade_kp_select_{grade}",
        )
        if st.button(
            "打开学习卡片", key=f"grade_kp_open_{grade}"
        ):
            st.query_params["kp"] = selected
            st.rerun()


@st.fragment
def _render_filters_and_groups(
    cards: list[KnowledgeCard],
    index: GradeIndex,
    spans: Mapping[str, tuple[str, ...]],
) -> None:
    """渲染年级与难度筛选、数量统计和分组列表。"""
    grade = st.selectbox(
        "年级",
        GRADE_OPTIONS,
        format_func=grade_label,
        key="grade_filter",
    )
    st.session_state["grade_last_selected"] = grade
    difficulty = st.selectbox(
        "难度",
        DIFFICULTY_OPTIONS,
        format_func=_difficulty_label,
        key="difficulty_filter",
    )
    _render_learning_entry(cards, spans, grade)
    filtered = _filtered_cards(cards, index, grade, difficulty)
    exercise_count = sum(len(card.exercises) for card in filtered)
    st.caption(
        f"共 {len(filtered)} 张卡片 · {exercise_count} 道题"
    )
    if not filtered:
        st.info("该年级/难度暂无卡片。")
        return

    groups = _grouped_cards(filtered, index)
    first = True
    for value in DIFFICULTY_VALUES + (UNCLASSIFIED,):
        group = groups.get(value) or []
        if not group:
            continue
        with st.expander(
            f"{_difficulty_label(value)} · {len(group)} 张卡片",
            expanded=first,
        ):
            for card in group:
                st.markdown(
                    f"- **{card.name}** · {card.course} · "
                    f"{card.chapter}"
                )
        first = False


def render_grade_page(
    cards: list[KnowledgeCard],
    index: GradeIndex,
    spans: Mapping[str, tuple[str, ...]],
    repository: Repository,
    consent: Consent,
    initial_grade: str | None = None,
) -> None:
    """年级筛选页；学习数据保持全局共享。"""
    st.subheader("按年级")
    st.caption(
        "按年级与难度筛选卡片；收据、错题本、复习队列仍全局共享，"
        "不按年级隔离。"
    )
    review_items = repository.list_review_items()
    today_end = end_of_local_day(datetime.now(timezone.utc))
    due_items = [item for item in review_items if item.due_at <= today_end]
    st.metric("今日待复习（跨年级）", str(len(due_items)))
    if due_items:
        preview = "；".join(
            item.mistake.stem for item in due_items[:3]
        )
        st.caption(f"跨年级已到期：{preview}")

    default_grade = load_default_grade(consent)
    if initial_grade in GRADE_OPTIONS:
        if st.session_state.get("grade_filter") != initial_grade:
            st.session_state["grade_filter"] = initial_grade
    elif "grade_filter" not in st.session_state:
        st.session_state["grade_filter"] = st.session_state.get(
            "grade_last_selected", default_grade
        )

    _render_filters_and_groups(cards, index, spans)
