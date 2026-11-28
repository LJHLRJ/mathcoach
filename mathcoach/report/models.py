"""可解释学情报告：结论、指标与证据锚点。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class EvidenceAnchor:
    """一条可回指的证据。"""

    kind: str
    id: str
    exercise_id: str
    card_id: str
    occurred_at: datetime
    snippet: str


@dataclass(frozen=True)
class ReportMetric:
    """结论引用的统计指标。"""

    id: str
    value: float
    unit: str
    label: str


@dataclass(frozen=True)
class ReportConclusion:
    """一条统计层结论及其证据。"""

    id: str
    kind: str
    statement: str
    metrics: tuple[ReportMetric, ...] = ()
    evidence: tuple[EvidenceAnchor, ...] = ()
    confidence: str = "medium"
    data_gaps: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExplainableReport:
    """一段时间窗口内的结论集合。"""

    start: datetime
    end: datetime
    conclusions: tuple[ReportConclusion, ...] = ()
    notes: tuple[str, ...] = ()
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
