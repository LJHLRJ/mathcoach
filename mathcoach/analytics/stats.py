"""只读统计：把现有持久化数据聚合为分析快照。"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from ..domain.hint_ladder import INDEPENDENT_MAX_LEVEL
from ..domain.models import (
    ErrorType,
    Independence,
    MasterySnapshot,
    MistakeEntry,
    Receipt,
    ReviewState,
)
from ..domain.receipt import RESTATEMENT_COMPLETE
from ..memory.report import build_error_trend, build_mastery_changes
from ..timeutil import end_of_local_day, local_day
from .models import (
    ANALYSIS_SCHEMA_VERSION,
    AnalysisRepository,
    AnalysisScope,
    AnalysisSnapshot,
    AnalysisWindow,
    CardSnapshot,
    DataQuality,
    ErrorCount,
    ErrorTrendView,
    MasteryDelta,
    MetricValue,
)

MINIMUM_SAMPLE = 5
MASTERY_CHANGE_LIMIT = 5


def _count(value: int, unit: str = "count") -> MetricValue:
    """构造计数指标。"""
    return MetricValue(value=value, n=value, numerator=value, unit=unit)


def _rate(numerator: int, denominator: int) -> MetricValue:
    """构造比例指标；分母为 0 时值为 None。"""
    value = round(numerator / denominator, 4) if denominator else None
    return MetricValue(
        value=value,
        n=denominator,
        numerator=numerator,
        denominator=denominator,
        unit="ratio",
    )


def _average(values: list[int], unit: str) -> MetricValue:
    """构造平均值指标；没有样本时值为 None。"""
    size = len(values)
    value = round(sum(values) / size, 2) if size else None
    return MetricValue(
        value=value,
        n=size,
        denominator=size,
        unit=unit,
    )


def _in_window(value: datetime, start: date, end: date) -> bool:
    """判断时间是否落在本地日期闭区间内。"""
    return start <= local_day(value) <= end


def _scope_filter(
    items: Iterable[Receipt] | Iterable[MistakeEntry],
    card_id: str | None,
) -> list:
    """按卡片过滤收据或错题。"""
    if card_id is None:
        return list(items)
    return [item for item in items if item.card_id == card_id]


def _top_errors(mistakes: list[MistakeEntry]) -> tuple[ErrorCount, ...]:
    """按顶层错因统计窗口内前三位。"""
    total = len(mistakes)
    if total == 0:
        return ()
    counter = Counter(mistake.error_type for mistake in mistakes)
    return tuple(
        ErrorCount(
            error_type=error_type,
            code=None,
            count=count,
            share=round(count / total, 4),
        )
        for error_type, count in counter.most_common(3)
    )


def _error_trend(
    mistakes: list[MistakeEntry], now: datetime, days: int
) -> ErrorTrendView:
    """复用现有周环比口径，转换为只读视图。"""
    trend = build_error_trend(mistakes, now, days=days)
    return ErrorTrendView(
        this_week=tuple(trend.this_week),
        last_week=tuple(trend.last_week),
        summary=trend.summary,
    )


def _mastery_deltas(
    history: list[MasterySnapshot], start: date, end: date
) -> tuple[MasteryDelta, ...]:
    """取窗口内全部掌握度变化，按变化绝对值排序。"""
    changes = build_mastery_changes(
        history, start, end, limit=max(len(history), MASTERY_CHANGE_LIMIT)
    )
    return tuple(
        MasteryDelta(
            card_id=change.card_id,
            before=round(change.before, 4),
            after=round(change.after, 4),
            delta=round(change.delta, 4),
        )
        for change in changes
    )


def _course_for(
    receipts: list[Receipt],
    mistakes: list[MistakeEntry],
) -> str:
    """从收据或错题中取课程名称。"""
    for receipt in receipts:
        if receipt.course:
            return receipt.course
    for mistake in mistakes:
        if mistake.course:
            return mistake.course
    return ""


def _by_card(
    repository: AnalysisRepository,
    receipts: list[Receipt],
    mistakes: list[MistakeEntry],
    deltas: tuple[MasteryDelta, ...],
) -> tuple[CardSnapshot, ...]:
    """按卡片汇总窗口内表现。"""
    receipts_by_card: dict[str, list[Receipt]] = defaultdict(list)
    mistakes_by_card: dict[str, list[MistakeEntry]] = defaultdict(list)
    for receipt in receipts:
        receipts_by_card[receipt.card_id].append(receipt)
    for mistake in mistakes:
        mistakes_by_card[mistake.card_id].append(mistake)

    delta_by_card = {item.card_id: item.delta for item in deltas}
    cards = sorted(set(receipts_by_card) | set(mistakes_by_card))
    snapshots: list[CardSnapshot] = []
    for card_id in cards:
        card_receipts = receipts_by_card.get(card_id, [])
        card_mistakes = mistakes_by_card.get(card_id, [])
        independent = sum(
            1
            for receipt in card_receipts
            if receipt.independence is Independence.INDEPENDENT
        )
        average_hint = (
            round(
                sum(receipt.max_hint_level for receipt in card_receipts)
                / len(card_receipts),
                2,
            )
            if card_receipts
            else None
        )
        error_counter = Counter(
            mistake.error_type for mistake in card_mistakes
        )
        top_error = (
            error_counter.most_common(1)[0][0] if error_counter else None
        )
        snapshots.append(
            CardSnapshot(
                card_id=card_id,
                course=_course_for(card_receipts, card_mistakes),
                receipts=len(card_receipts),
                mistakes=len(card_mistakes),
                independent=independent,
                average_hint_level=average_hint,
                mastery=repository.get_mastery(card_id),
                mastery_delta=delta_by_card.get(card_id),
                top_error=top_error,
            )
        )
    snapshots.sort(
        key=lambda item: (-item.mistakes, -item.receipts, item.card_id)
    )
    return tuple(snapshots)


def build_snapshot(
    repository: AnalysisRepository,
    now: datetime,
    days: int = 7,
    card_id: str | None = None,
) -> AnalysisSnapshot:
    """聚合收据、错题、复习与掌握度，生成只读分析快照。

    统计窗口按本地日期闭区间计算；所有查询都通过只读接口完成。

    Args:
        repository: 只读仓储。
        now: 窗口结束的基准时间。
        days: 窗口天数，必须大于 0。
        card_id: 限定卡片；None 表示全部卡片。

    Returns:
        ``AnalysisSnapshot``。

    Raises:
        ValueError: ``days`` 小于 1。
    """
    if days < 1:
        raise ValueError("days 必须大于 0")

    end = local_day(now)
    start = end - timedelta(days=days - 1)
    all_receipts = _scope_filter(
        repository.list_receipts(limit=None), card_id
    )
    all_mistakes = _scope_filter(
        repository.list_mistakes(limit=None), card_id
    )
    receipts = [
        receipt
        for receipt in all_receipts
        if _in_window(receipt.created_at, start, end)
    ]
    mistakes = [
        mistake
        for mistake in all_mistakes
        if _in_window(mistake.created_at, start, end)
    ]

    review_items = [
        item
        for item in repository.list_review_items()
        if card_id is None or item.mistake.card_id == card_id
    ]
    due_today = sum(
        1 for item in review_items if item.due_at <= end_of_local_day(now)
    )

    history = repository.list_mastery_history(card_id)
    all_deltas = _mastery_deltas(history, start, end)
    deltas = all_deltas[:MASTERY_CHANGE_LIMIT]

    independent = sum(
        1
        for receipt in receipts
        if receipt.independence is Independence.INDEPENDENT
    )
    hinted = sum(
        1
        for receipt in receipts
        if receipt.max_hint_level > INDEPENDENT_MAX_LEVEL
    )
    concept_wrong = sum(
        1 for mistake in mistakes if mistake.error_type is ErrorType.CONCEPT
    )
    reviewed_with_quality = [
        receipt
        for receipt in receipts
        if receipt.restatement_quality is not None
    ]
    complete_restatements = sum(
        1
        for receipt in reviewed_with_quality
        if receipt.restatement_quality == RESTATEMENT_COMPLETE
    )
    active_days = {
        local_day(receipt.created_at) for receipt in receipts
    } | {local_day(mistake.created_at) for mistake in mistakes}
    review_counts = Counter(mistake.review_state for mistake in all_mistakes)

    metrics = {
        "receipts.count": _count(len(receipts)),
        "receipts.independent_rate": _rate(independent, len(receipts)),
        "receipts.semi_independent_rate": _rate(
            len(receipts) - independent, len(receipts)
        ),
        "hints.average_max_level": _average(
            [receipt.max_hint_level for receipt in receipts], "level"
        ),
        "hints.dependency_rate": _rate(hinted, len(receipts)),
        "mistakes.count": _count(len(mistakes)),
        "mistakes.concept_share": _rate(concept_wrong, len(mistakes)),
        "review.due_today": _count(due_today),
        "review.unreviewed_rate": _rate(
            review_counts[ReviewState.UNREVIEWED], len(all_mistakes)
        ),
        "review.reviewing_rate": _rate(
            review_counts[ReviewState.REVIEWING], len(all_mistakes)
        ),
        "review.mastered_rate": _rate(
            review_counts[ReviewState.MASTERED], len(all_mistakes)
        ),
        "activity.active_days": _count(len(active_days), "days"),
        "restatement.complete_rate": _rate(
            complete_restatements, len(reviewed_with_quality)
        ),
        "mastery.changed_cards": _count(len(all_deltas)),
    }

    sample_size = len(receipts) + len(mistakes)
    data_quality = DataQuality(
        attempt_events_available=False,
        event_coverage_start=None,
        sample_size=sample_size,
        minimum_sample_met=sample_size >= MINIMUM_SAMPLE,
        notes=(
            "逐次作答事件尚未采集：正确率、单次用时与逐次提示过程不可用。",
            "统计基于收据、错题与掌握度快照，未生成收据的尝试可能被低估。",
        ),
    )

    return AnalysisSnapshot(
        schema_version=ANALYSIS_SCHEMA_VERSION,
        window=AnalysisWindow(start=start, end=end, days=days),
        scope=AnalysisScope(card_id=card_id),
        generated_at=now,
        metrics=metrics,
        errors=_top_errors(mistakes),
        error_trend=_error_trend(all_mistakes, now, days),
        mastery_changes=deltas,
        by_card=_by_card(repository, receipts, mistakes, deltas),
        data_quality=data_quality,
    )
