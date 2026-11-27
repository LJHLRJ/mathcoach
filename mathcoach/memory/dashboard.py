"""学习仪表盘：只读聚合，不写任何数据。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from ..domain.models import Independence, ReviewState
from ..timeutil import end_of_local_day
from .repository import Repository


@dataclass(frozen=True)
class DashboardSummary:
    """仪表盘聚合结果。

    Attributes:
        receipts: 收据总数。
        independent: 独立完成数。
        semi_independent: 半独立完成数。
        mistakes: 错题总数。
        unreviewed: 未复习的错题数。
        reviewing: 复习中的错题数。
        mastered: 已掌握的错题数。
        due_today: 今天到期的复习项数。
        average_hint_level: 平均最高提示层级。
        top_errors: 出现最多的三类错因。
        top_courses: 错题最多的三门课程。
    """

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


def build_dashboard(repository: Repository, now: datetime) -> DashboardSummary:
    """聚合收据、错题与复习队列，生成仪表盘数据。

    只读：收据、错题取全量，复习项取当前队列；错因与课程各取前 3。

    Args:
        repository: 仓储。
        now: 计算“今天到期”的基准时间。

    Returns:
        ``DashboardSummary``。
    """
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
    today_end = end_of_local_day(now)

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
