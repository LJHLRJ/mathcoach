"""周报与错因趋势：跨会话只读聚合。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..domain.models import ErrorType, Independence, MistakeEntry
from ..domain.prerequisites import MistakeStat
from ..timeutil import end_of_local_day, local_day
from .repository import Repository


@dataclass(frozen=True)
class ErrorTrend:
    """错因趋势对比。

    Attributes:
        this_week: 本期错因与次数，按次数降序。
        last_week: 上期错因与次数。
        summary: 一句趋势说明。
    """

    this_week: tuple[tuple[str, int], ...]
    last_week: tuple[tuple[str, int], ...]
    summary: str


@dataclass(frozen=True)
class WeeklyReport:
    """周报聚合结果。

    Attributes:
        start: 起始日期。
        end: 结束日期。
        receipts: 收据数。
        independent: 独立完成数。
        mistakes: 错题数。
        due_today: 今天到期的复习项数。
        average_hint_level: 平均最高提示层级。
        daily_receipts: 每日收据数，按日期补齐。
        top_errors: 出现最多的三类错因。
        trend: 错因趋势。
    """

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


def build_mistake_stats(mistakes: list[MistakeEntry]) -> dict[str, MistakeStat]:
    """按卡片聚合错题总数与概念错数，供先修链诊断使用。"""
    counters: dict[str, list[int]] = {}
    for mistake in mistakes:
        current = counters.setdefault(mistake.card_id, [0, 0])
        current[0] += 1
        if mistake.error_type is ErrorType.CONCEPT:
            current[1] += 1
    return {
        card_id: MistakeStat(total=total, concept_wrong=concept)
        for card_id, (total, concept) in counters.items()
    }


def build_error_trend(
    mistakes: list[MistakeEntry], now: datetime, days: int = 7
) -> ErrorTrend:
    """对比相邻两个窗口的错因分布。

    本期为最近 ``days`` 天（含今天），上期为紧邻的前 ``days`` 天；
    本期为空时给一句无新增错题的说明。

    Args:
        mistakes: 错题。
        now: 计算窗口的基准时间。
        days: 单个窗口的天数。

    Returns:
        ``ErrorTrend``。
    """
    today = local_day(now)
    this_start = today - timedelta(days=days - 1)
    last_start = this_start - timedelta(days=days)
    last_end = this_start - timedelta(days=1)

    this_counter: Counter[str] = Counter()
    last_counter: Counter[str] = Counter()
    for mistake in mistakes:
        day = local_day(mistake.created_at)
        if this_start <= day <= today:
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
    """生成最近 ``days`` 天的学习周报。

    收据与错题按本地日期过滤；每日收据数补齐没有数据的日期；
    到期数取当前复习队列里今天到期的条目。

    Args:
        repository: 仓储。
        now: 计算窗口的基准时间。
        days: 统计天数。

    Returns:
        ``WeeklyReport``。
    """
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
