"""学习仪表盘：只读聚合，不写任何数据。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from ..domain.models import Independence, ReviewState
from .repository import Repository


@dataclass(frozen=True)
class DashboardSummary:
    receipts: int
    independent: int
    semi_independent: int
    mistakes: int
    unreviewed: int
    reviewing: int
    mastered: int
    due_today: int
    average_hint_level: float
    top_errors: tuple[tuple[str, int], ...]
    top_courses: tuple[tuple[str, int], ...]


def _end_of_day(value: datetime) -> datetime:
    return value.replace(hour=23, minute=59, second=59, microsecond=999999)


def build_dashboard(repository: Repository, now: datetime) -> DashboardSummary:
    receipts = repository.list_receipts(limit=None)
    mistakes = repository.list_mistakes(limit=None)
    review_items = repository.list_review_items()

    independent = sum(
        1 for receipt in receipts if receipt.independence is Independence.INDEPENDENT
    )
    average = (
        round(sum(receipt.max_hint_level for receipt in receipts) / len(receipts), 1)
        if receipts
        else 0.0
    )
    errors = Counter(mistake.error_type.value for mistake in mistakes)
    courses = Counter(mistake.course for mistake in mistakes)
    today_end = _end_of_day(now)

    return DashboardSummary(
        receipts=len(receipts),
        independent=independent,
        semi_independent=len(receipts) - independent,
        mistakes=len(mistakes),
        unreviewed=sum(
            1 for mistake in mistakes if mistake.review_state is ReviewState.UNREVIEWED
        ),
        reviewing=sum(
            1 for mistake in mistakes if mistake.review_state is ReviewState.REVIEWING
        ),
        mastered=sum(
            1 for mistake in mistakes if mistake.review_state is ReviewState.MASTERED
        ),
        due_today=sum(1 for item in review_items if item.due_at <= today_end),
        average_hint_level=average,
        top_errors=tuple(errors.most_common(3)),
        top_courses=tuple(courses.most_common(3)),
    )
