"""复习调度：纯函数，可单测。

规则（设计文档 §6）：
- 新错题当天进入复习清单；
- 独立做对一次 → 明天再复习；连续两次独立做对 → 已掌握并退出清单；
- 半独立做对 → 连续独立计数清零，三天后再复习；
- 清单按“今天 / 明天 / 三天后”分档，每档不超过 3 项。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from ..domain.models import MistakeEntry, ReviewItem, ReviewState
from ..domain.spaced_repetition import Bucket, bucket_for
from ..timeutil import end_of_local_day, start_of_local_day_after

REVIEW_LIMIT = 3
MASTERY_STREAK = 2


@dataclass(frozen=True)
class ReviewPlan:
    today: tuple[ReviewItem, ...]
    tomorrow: tuple[ReviewItem, ...]
    in_three_days: tuple[ReviewItem, ...]


def next_review(
    entry: MistakeEntry, independent: bool, now: datetime
) -> tuple[ReviewState, int, int, datetime | None]:
    """返回 (新复习状态, 复习次数, 连续独立做对次数, 下次到期时间)。"""
    if entry.review_state is ReviewState.MASTERED:
        return ReviewState.MASTERED, entry.review_count, entry.consecutive_correct, None

    review_count = entry.review_count + 1
    if independent:
        streak = entry.consecutive_correct + 1
        if streak >= MASTERY_STREAK:
            return ReviewState.MASTERED, review_count, streak, None
        return (
            ReviewState.REVIEWING,
            review_count,
            streak,
            start_of_local_day_after(now, 1),
        )

    return (
        ReviewState.REVIEWING,
        review_count,
        0,
        start_of_local_day_after(now, 3),
    )


def build_plan(
    items: Iterable[ReviewItem], now: datetime, limit: int = REVIEW_LIMIT
) -> ReviewPlan:
    """把待复习项分到三档，每档最多 limit 项。"""
    today_end = end_of_local_day(now)
    tomorrow_end = end_of_local_day(now + timedelta(days=1))
    three_day_end = end_of_local_day(now + timedelta(days=3))
    buckets: dict[str, list[ReviewItem]] = {
        "today": [],
        "tomorrow": [],
        "in_three_days": [],
    }

    for item in sorted(items, key=lambda current: current.due_at):
        if item.mistake.review_state is ReviewState.MASTERED:
            continue
        if item.due_at <= today_end:
            bucket = "today"
        elif item.due_at <= tomorrow_end:
            bucket = "tomorrow"
        elif item.due_at <= three_day_end:
            bucket = "in_three_days"
        else:
            continue
        if len(buckets[bucket]) < limit:
            buckets[bucket].append(item)

    return ReviewPlan(
        today=tuple(buckets["today"]),
        tomorrow=tuple(buckets["tomorrow"]),
        in_three_days=tuple(buckets["in_three_days"]),
    )


def build_review_queue(repo, now: datetime) -> dict[Bucket, list[MistakeEntry]]:
    """只返回 next_review_at <= now 的条目，按 interval_days 映射到三档。"""
    queue: dict[Bucket, list[MistakeEntry]] = defaultdict(list)
    for item in repo.list_due_mistakes(now):
        queue[bucket_for(item.interval_days)].append(item)
    return dict(queue)
