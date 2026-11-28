"""分析快照数据结构与只读仓储契约。"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from ..domain.models import (
    ErrorType,
    MasterySnapshot,
    MistakeEntry,
    Receipt,
    ReviewItem,
)
from .errors import ErrorCode

ANALYSIS_SCHEMA_VERSION = "analysis-snapshot/1"


class AnalysisRepository(Protocol):
    """分析层需要的最小只读接口；不包含任何写入方法。"""

    def list_receipts(self, limit: int | None = 50) -> list[Receipt]:
        """按时间倒序返回收据。"""
        ...

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]:
        """按创建时间倒序返回错题。"""
        ...

    def list_review_items(self) -> list[ReviewItem]:
        """返回当前待复习项。"""
        ...

    def list_mastery_history(
        self, card_id: str | None = None
    ) -> list[MasterySnapshot]:
        """按记录时间升序返回掌握度快照。"""
        ...

    def get_mastery(self, card_id: str) -> float | None:
        """读取当前掌握概率。"""
        ...


@dataclass(frozen=True)
class AnalysisWindow:
    """统计窗口，按本地日期闭区间表示。

    Attributes:
        start: 起始日期。
        end: 结束日期。
        days: 窗口天数。
    """

    start: date
    end: date
    days: int

    def to_dict(self) -> dict[str, Any]:
        """转为可直接序列化的映射。"""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "days": self.days,
            "timezone": "local",
        }


@dataclass(frozen=True)
class AnalysisScope:
    """统计范围。

    Attributes:
        card_id: 限定卡片；None 表示全部卡片。
    """

    card_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转为可直接序列化的映射。"""
        return {"card_id": self.card_id}


@dataclass(frozen=True)
class MetricValue:
    """一个带样本量的统计指标。

    Attributes:
        value: 指标值；无法计算时为 None。
        n: 参与计算的样本量。
        numerator: 分子；计数类指标与 value 相同。
        denominator: 分母；计数类指标为 None。
        unit: 单位或口径说明，如 ``ratio`` / ``seconds`` / ``level``。
    """

    value: float | int | None
    n: int = 0
    numerator: int | None = None
    denominator: int | None = None
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可直接序列化的映射。"""
        return {
            "value": self.value,
            "n": self.n,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class ErrorCount:
    """一个错因的计数。

    Attributes:
        error_type: 顶层错因。
        code: 子类编码；当前汇总数据没有子类时为 None。
        count: 次数。
        share: 占窗口错题总数的比例。
    """

    error_type: ErrorType
    code: ErrorCode | None
    count: int
    share: float

    def to_dict(self) -> dict[str, Any]:
        """转为可直接序列化的映射。"""
        code = getattr(self.code, "value", self.code)
        return {
            "error_type": self.error_type.value,
            "code": code,
            "count": self.count,
            "share": self.share,
        }


@dataclass(frozen=True)
class ErrorTrendView:
    """错因周环比。

    Attributes:
        this_week: 本期错因与次数。
        last_week: 上期错因与次数。
        summary: 一句趋势说明。
    """

    this_week: tuple[tuple[str, int], ...]
    last_week: tuple[tuple[str, int], ...]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """转为可直接序列化的映射。"""
        return {
            "this_week": [list(item) for item in self.this_week],
            "last_week": [list(item) for item in self.last_week],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class MasteryDelta:
    """一张卡片在窗口内的掌握度变化。

    Attributes:
        card_id: 卡片 ID。
        before: 窗口前基线。
        after: 窗口内最新值。
        delta: 变化量。
    """

    card_id: str
    before: float
    after: float
    delta: float

    def to_dict(self) -> dict[str, Any]:
        """转为可直接序列化的映射。"""
        return {
            "card_id": self.card_id,
            "before": self.before,
            "after": self.after,
            "delta": self.delta,
        }


@dataclass(frozen=True)
class CardSnapshot:
    """单张卡片在窗口内的表现。

    Attributes:
        card_id: 卡片 ID。
        course: 课程名称。
        receipts: 收据数。
        mistakes: 错题数。
        independent: 独立完成收据数。
        average_hint_level: 平均最高提示层级。
        mastery: 当前掌握概率。
        mastery_delta: 窗口内掌握度变化。
        top_error: 窗口内最多的顶层错因。
    """

    card_id: str
    course: str
    receipts: int
    mistakes: int
    independent: int
    average_hint_level: float | None
    mastery: float | None
    mastery_delta: float | None
    top_error: ErrorType | None

    def to_dict(self) -> dict[str, Any]:
        """转为可直接序列化的映射。"""
        return {
            "card_id": self.card_id,
            "course": self.course,
            "receipts": self.receipts,
            "mistakes": self.mistakes,
            "independent": self.independent,
            "average_hint_level": self.average_hint_level,
            "mastery": self.mastery,
            "mastery_delta": self.mastery_delta,
            "top_error": self.top_error.value if self.top_error else None,
        }


@dataclass(frozen=True)
class DataQuality:
    """数据完整度说明，供叙事层避免过度推断。

    Attributes:
        attempt_events_available: 是否存在逐次作答事件。
        event_coverage_start: 事件覆盖起始日期；没有事件时为 None。
        sample_size: 窗口内收据与错题样本量。
        minimum_sample_met: 是否达到最小样本门槛。
        notes: 口径与缺口说明。
    """

    attempt_events_available: bool
    event_coverage_start: str | None
    sample_size: int
    minimum_sample_met: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """转为可直接序列化的映射。"""
        return {
            "attempt_events_available": self.attempt_events_available,
            "event_coverage_start": self.event_coverage_start,
            "sample_size": self.sample_size,
            "minimum_sample_met": self.minimum_sample_met,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class AnalysisSnapshot:
    """一次只读统计的完整结果。

    Attributes:
        schema_version: 快照版本。
        window: 统计窗口。
        scope: 统计范围。
        generated_at: 生成时间。
        metrics: 指标 ID 到指标值的映射。
        errors: 窗口内错因计数。
        error_trend: 错因周环比。
        mastery_changes: 掌握度变化。
        by_card: 单卡表现。
        data_quality: 数据完整度。
    """

    schema_version: str
    window: AnalysisWindow
    scope: AnalysisScope
    generated_at: datetime
    metrics: Mapping[str, MetricValue]
    errors: tuple[ErrorCount, ...]
    error_trend: ErrorTrendView
    mastery_changes: tuple[MasteryDelta, ...]
    by_card: tuple[CardSnapshot, ...]
    data_quality: DataQuality

    def to_dict(self) -> dict[str, Any]:
        """转为可直接 JSON 序列化的映射。"""
        return {
            "schema_version": self.schema_version,
            "window": self.window.to_dict(),
            "scope": self.scope.to_dict(),
            "generated_at": self.generated_at.isoformat(),
            "metrics": {
                key: value.to_dict() for key, value in self.metrics.items()
            },
            "errors": [item.to_dict() for item in self.errors],
            "error_trend": self.error_trend.to_dict(),
            "mastery_changes": [
                item.to_dict() for item in self.mastery_changes
            ],
            "by_card": [item.to_dict() for item in self.by_card],
            "data_quality": self.data_quality.to_dict(),
        }
