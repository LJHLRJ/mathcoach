"""周报与错因趋势：跨会话只读聚合。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..domain.models import Independence, MistakeEntry
from ..timeutil import end_of_local_day, local_day
from .repository import Repository


@dataclass(frozen=True)
class ErrorTrend:
    this_week: tuple[tuple[str, int], ...]
    last_week: tuple[tuple[str, int], ...]
    summary: str


@dataclass(frozen=True)
class WeeklyReport:
    start: date
    end: date
    receipts: int
    independent: int
    mistakes: int
    due_today: int
    average_hint_level: float
    daily_receipts: tuple[tuple[str, int], ...]
    top_errors: tuple[tuple[str, int], ...]
    trend: ErrorTrend


def build_error_trend(
    mistakes: list[MistakeEntry], now: datetime, days: int = 7
) -> ErrorTrend:
    today = local_day(now)
    this_start = today - timedelta(days=days - 1)
    last_start = this_start - timedelta(days=days)
    last_end = this_start - timedelta(days=1)

    this_counter: Counter[str] = Counter()
    last_counter: Counter[str] = Counter()
    for mistake in mistakes:
        day = local_day(mistake.created_at)
        if day >= this_start:
            this_counter[mistake.error_type.value] += 1
        elif last_start <= day <= last_end:
            last_counter[mistake.error_type.value] += 1

    this_week = tuple(this_counter.most_common())
    last_week = tuple(last_counter.most_common())
    if not this_week:
        summary = f"最近 {days} 天没有新增错题。"
    else:
        parts = []
        for name, count in this_week:
            delta = count - last_counter.get(name, 0)
            sign = f"+{delta}" if delta > 0 else str(delta)
            parts.append(f"{name} {count} 次（较上周 {sign}）")
        summary = "；".join(parts)
    return ErrorTrend(this_week=this_week, last_week=last_week, summary=summary)


def build_weekly_report(
    repository: Repository, now: datetime, days: int = 7
) -> WeeklyReport:
    end = local_day(now)
    start = end - timedelta(days=days - 1)

    receipts = [
        receipt
        for receipt in repository.list_receipts(limit=None)
        if start <= local_day(receipt.created_at) <= end
    ]
    mistakes = [
        mistake
        for mistake in repository.list_mistakes(limit=None)
        if start <= local_day(mistake.created_at) <= end
    ]
    daily = Counter(
        local_day(receipt.created_at).isoformat() for receipt in receipts
    )
    daily_receipts = tuple(
        (
            (start + timedelta(days=offset)).isoformat(),
            daily.get((start + timedelta(days=offset)).isoformat(), 0),
        )
        for offset in range(days)
    )
    errors = Counter(mistake.error_type.value for mistake in mistakes)
    average = (
        round(sum(receipt.max_hint_level for receipt in receipts) / len(receipts), 1)
        if receipts
        else 0.0
    )
    due_today = sum(
        1
        for item in repository.list_review_items()
        if item.due_at <= end_of_local_day(now)
    )

    return WeeklyReport(
        start=start,
        end=end,
        receipts=len(receipts),
        independent=sum(
            1
            for receipt in receipts
            if receipt.independence is Independence.INDEPENDENT
        ),
        mistakes=len(mistakes),
        due_today=due_today,
        average_hint_level=average,
        daily_receipts=daily_receipts,
        top_errors=tuple(errors.most_common(3)),
        trend=build_error_trend(
            repository.list_mistakes(limit=None), now, days=days
        ),
    )
