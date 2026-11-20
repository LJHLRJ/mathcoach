"""智能复习包：优先到期错题，不足 5 题时用同课程练习补齐。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.models import KnowledgeCard
from ..session.daily import DailyQuestion
from .repository import Repository

REVIEW_PACKAGE_SIZE = 5
REVIEW_PACKAGE_LIMIT_S = 900


@dataclass(frozen=True)
class ReviewPackage:
    questions: tuple[DailyQuestion, ...]
    reason: str


def _end_of_day(value: datetime) -> datetime:
    return value.replace(hour=23, minute=59, second=59, microsecond=999999)


def build_review_package(
    repository: Repository,
    cards: list[KnowledgeCard],
    now: datetime,
    count: int = REVIEW_PACKAGE_SIZE,
) -> ReviewPackage:
    by_exercise = {
        exercise.id: (card, exercise)
        for card in cards
        for exercise in card.exercises
    }
    items = repository.list_review_items()
    if not items:
        return ReviewPackage((), "暂无待复习错题，先完成一次小测。")

    today_end = _end_of_day(now)
    ordered = sorted(
        items,
        key=lambda item: (item.due_at > today_end, item.due_at),
    )
    selected: list[DailyQuestion] = []
    seen: set[str] = set()
    for item in ordered:
        pair = by_exercise.get(item.mistake.exercise_id)
        if pair is None or item.mistake.exercise_id in seen:
            continue
        card, exercise = pair
        selected.append(DailyQuestion(card, exercise))
        seen.add(exercise.id)
        if len(selected) >= count:
            break

    if len(selected) < count:
        prefer_cards = {question.card.id for question in selected}
        candidates = sorted(
            (
                (card, exercise)
                for card in cards
                for exercise in card.exercises
                if exercise.id not in seen
            ),
            key=lambda pair: (
                pair[0].id not in prefer_cards,
                pair[0].id,
                pair[1].id,
            ),
        )
        for card, exercise in candidates:
            selected.append(DailyQuestion(card, exercise))
            seen.add(exercise.id)
            if len(selected) >= count:
                break

    due_count = sum(1 for item in items if item.due_at <= today_end)
    reason = (
        f"从 {len(items)} 道待复习错题中优先选取 {due_count} 道到期题，"
        f"共 {len(selected)} 题。"
    )
    return ReviewPackage(tuple(selected), reason)
