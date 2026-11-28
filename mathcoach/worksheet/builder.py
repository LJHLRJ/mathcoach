"""可打印练习单：从当前卡片、到期错题或错题本生成只读题目集。

只读取题库与学习档案，不写 BKT、FSRS、错题或复习状态。
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from ..domain.models import (
    ErrorType,
    Exercise,
    KnowledgeCard,
    MistakeEntry,
)
from ..memory.repository import Repository
from ..timeutil import end_of_local_day

DEFAULT_COUNT = 10
MAX_COUNT = 30


class WorksheetSource(str, Enum):
    """练习单题目来源。"""

    CURRENT_CARD = "current_card"
    SAME_TOPIC = "same_topic"
    DUE_REVIEW = "due_review"
    MISTAKES = "mistakes"
    SMART_PLAN = "smart_plan"


@dataclass(frozen=True)
class WorksheetItem:
    """练习单中的一道题。

    Attributes:
        exercise: 题目。
        card: 所属知识点卡；旧数据可能缺失。
        card_name: 卡片名称，缺失时用卡片 ID。
        course: 课程名称。
        source_label: 来源标签，如“错题”“待复习”。
        error_type: 错因；非错题来源时为 None。
    """

    exercise: Exercise
    card: KnowledgeCard | None
    card_name: str
    course: str
    source_label: str
    error_type: ErrorType | None = None


@dataclass(frozen=True)
class Worksheet:
    """一次生成的练习单。

    Attributes:
        title: 练习单标题。
        source: 题目来源枚举。
        source_label: 来源说明。
        items: 题目列表，已去重并限量。
        include_answers: 是否附答案页。
        include_solutions: 答案页是否附解题思路。
        generated_at: 生成时间。
        notes: 生成过程中的提示，如“今天没有到期错题”。
    """

    title: str
    source: WorksheetSource
    source_label: str
    items: tuple[WorksheetItem, ...]
    include_answers: bool
    include_solutions: bool
    generated_at: datetime
    notes: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        """题目数量。"""
        return len(self.items)


def _exercise_from_snapshot(entry: MistakeEntry) -> Exercise:
    """题目不在题库时，用错题快照还原一道题。"""
    snapshot = entry.exercise_snapshot
    return Exercise(
        id=entry.exercise_id,
        card_id=entry.card_id,
        kind=entry.exercise_type,
        stem=entry.stem,
        answer=entry.correct_answer,
        solution_outline=str(snapshot.get("solution_outline") or ""),
        options=tuple(snapshot.get("options") or ()),
        variants=tuple(snapshot.get("variants") or ()),
    )


def _find_exercise(
    cards: Sequence[KnowledgeCard], exercise_id: str
) -> tuple[Exercise, KnowledgeCard] | None:
    """在题库中按 ID 找题与所属卡片。"""
    for card in cards:
        for exercise in card.exercises:
            if exercise.id == exercise_id:
                return exercise, card
    return None


def _item_from_mistake(
    entry: MistakeEntry,
    cards: Sequence[KnowledgeCard],
    cards_by_id: dict[str, KnowledgeCard],
    source_label: str,
) -> tuple[WorksheetItem, bool]:
    """把错题转成练习单题目；返回是否使用了快照。"""
    found = _find_exercise(cards, entry.exercise_id)
    used_snapshot = found is None
    if found is None:
        exercise = _exercise_from_snapshot(entry)
        card = cards_by_id.get(entry.card_id)
    else:
        exercise, card = found
    return (
        WorksheetItem(
            exercise=exercise,
            card=card,
            card_name=card.name if card is not None else entry.card_id,
            course=card.course if card is not None else entry.course,
            source_label=source_label,
            error_type=entry.error_type,
        ),
        used_snapshot,
    )


def _unique(items: Sequence[WorksheetItem]) -> list[WorksheetItem]:
    """按题目 ID 去重，保留首次出现的题目。"""
    seen: set[str] = set()
    unique: list[WorksheetItem] = []
    for item in items:
        if item.exercise.id in seen:
            continue
        seen.add(item.exercise.id)
        unique.append(item)
    return unique


def _current_card_items(
    cards: Sequence[KnowledgeCard], card_id: str | None
) -> tuple[list[WorksheetItem], str]:
    """取当前卡片的全部题目。"""
    if card_id is None:
        return [], "未选择卡片"
    card = next((item for item in cards if item.id == card_id), None)
    if card is None:
        return [], "当前卡片不在题库中"
    items = [
        WorksheetItem(
            exercise=exercise,
            card=card,
            card_name=card.name,
            course=card.course,
            source_label="当前卡片",
        )
        for exercise in card.exercises
    ]
    return items, f"当前卡片：{card.name}"


def _card_items(card: KnowledgeCard) -> list[WorksheetItem]:
    """把一张卡的全部题目转成练习单题目。"""
    return [
        WorksheetItem(
            exercise=exercise,
            card=card,
            card_name=card.name,
            course=card.course,
            source_label="同章节/同课程",
        )
        for exercise in card.exercises
    ]


def _same_topic_items(
    cards: Sequence[KnowledgeCard], card_id: str | None
) -> tuple[list[WorksheetItem], str]:
    """当前卡片优先，其次同章节，最后同课程。"""
    if card_id is None:
        return [], "未选择卡片"
    current = next((item for item in cards if item.id == card_id), None)
    if current is None:
        return [], "当前卡片不在题库中"
    chapter_cards = [
        card
        for card in cards
        if card.id != current.id
        and card.stage is current.stage
        and card.course == current.course
        and card.chapter == current.chapter
    ]
    course_cards = [
        card
        for card in cards
        if card.id != current.id
        and card.stage is current.stage
        and card.course == current.course
        and card.chapter != current.chapter
    ]
    items = _card_items(current)
    for card in chapter_cards:
        items.extend(_card_items(card))
    for card in course_cards:
        items.extend(_card_items(card))
    return items, f"同章节/同课程：{current.name}"


def _due_review_items(
    repository: Repository,
    cards: Sequence[KnowledgeCard],
    now: datetime,
) -> tuple[list[WorksheetItem], str, list[str]]:
    """取今天到期的待复习错题。"""
    cards_by_id = {card.id: card for card in cards}
    today_end = end_of_local_day(now)
    items: list[WorksheetItem] = []
    used_snapshot = False
    for review in repository.list_review_items():
        if review.due_at > today_end:
            continue
        item, snapshot = _item_from_mistake(
            review.mistake, cards, cards_by_id, "待复习"
        )
        items.append(item)
        used_snapshot = used_snapshot or snapshot
    notes = ["部分题目不在题库中，已用错题快照还原。"] if used_snapshot else []
    if not items:
        notes.append("今天没有到期的待复习错题。")
    return items, "待复习错题", notes


def _mistake_items(
    repository: Repository,
    cards: Sequence[KnowledgeCard],
) -> tuple[list[WorksheetItem], str, list[str]]:
    """取错题本中未掌握的错题。"""
    cards_by_id = {card.id: card for card in cards}
    items: list[WorksheetItem] = []
    used_snapshot = False
    for entry in repository.list_mistakes(
        limit=None, include_mastered=False
    ):
        item, snapshot = _item_from_mistake(
            entry, cards, cards_by_id, "错题"
        )
        items.append(item)
        used_snapshot = used_snapshot or snapshot
    notes = ["部分题目不在题库中，已用错题快照还原。"] if used_snapshot else []
    if not items:
        notes.append("错题本中暂无未掌握的错题。")
    return items, "错题本", notes


def build_worksheet(
    cards: Sequence[KnowledgeCard],
    *,
    source: WorksheetSource,
    repository: Repository | None = None,
    current_card_id: str | None = None,
    count: int = DEFAULT_COUNT,
    include_answers: bool = True,
    include_solutions: bool = False,
    title: str = "数学练习单",
    now: datetime | None = None,
) -> Worksheet:
    """按来源生成练习单，不写任何学习状态。

    Args:
        cards: 全部知识点卡。
        source: 题目来源。
        repository: 学习档案；待复习与错题来源必填。
        current_card_id: 当前卡片 ID，仅当前卡片来源使用。
        count: 题目上限，夹在 1–30。
        include_answers: 是否附答案页。
        include_solutions: 答案页是否附解题思路；未附答案时不生效。
        title: 练习单标题。
        now: 生成时间，缺省为当前 UTC 时间。

    Returns:
        ``Worksheet``；无可用题目时 ``items`` 为空并带提示。
    """
    safe_count = max(1, min(MAX_COUNT, int(count)))
    moment = now or datetime.now(timezone.utc)
    notes: list[str] = []
    if source is WorksheetSource.CURRENT_CARD:
        items, source_label = _current_card_items(cards, current_card_id)
    elif source is WorksheetSource.SAME_TOPIC:
        items, source_label = _same_topic_items(cards, current_card_id)
    elif source is WorksheetSource.DUE_REVIEW and repository is not None:
        items, source_label, notes = _due_review_items(
            repository, cards, moment
        )
    elif source is WorksheetSource.MISTAKES and repository is not None:
        items, source_label, notes = _mistake_items(repository, cards)
    else:
        items, source_label = [], "未连接学习档案"

    unique = _unique(items)
    if len(unique) > safe_count:
        unique = unique[:safe_count]
        notes.append(f"已按题目上限截取前 {safe_count} 题。")
    if (
        source is WorksheetSource.SAME_TOPIC
        and unique
        and len(unique) < safe_count
    ):
        notes.append(
            f"同章节/同课程可用题目不足 {safe_count} 题，"
            f"已生成 {len(unique)} 题。"
        )
    if not unique:
        notes.append("暂无可生成的题目。")
    return Worksheet(
        title=title,
        source=source,
        source_label=source_label,
        items=tuple(unique),
        include_answers=include_answers,
        include_solutions=include_solutions and include_answers,
        generated_at=moment,
        notes=tuple(dict.fromkeys(notes)),
    )
