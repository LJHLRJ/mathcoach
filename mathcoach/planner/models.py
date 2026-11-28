"""智能练习册：选题计划的数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..domain.models import Exercise, KnowledgeCard


class PlanReason(str, Enum):
    """单道题的选题理由。"""

    DUE_REVIEW = "due_review"
    WEAK_KC = "weak_kc"
    REPEATED_ERROR = "repeated_error"
    TRANSFER = "transfer"
    COVERAGE = "coverage"
    FALLBACK = "fallback"


REASON_LABELS = {
    PlanReason.DUE_REVIEW: "到期复习",
    PlanReason.WEAK_KC: "薄弱知识点",
    PlanReason.REPEATED_ERROR: "重复错因",
    PlanReason.TRANSFER: "结构迁移",
    PlanReason.COVERAGE: "新覆盖",
    PlanReason.FALLBACK: "基础练习",
}


@dataclass(frozen=True)
class PlanItem:
    """计划中的一道题及其选择理由。"""

    exercise: Exercise
    card: KnowledgeCard
    kc_ids: tuple[str, ...] = ()
    reason_codes: tuple[PlanReason, ...] = ()
    reason_text: str = ""
    score: float = 0.0
    is_transfer: bool = False


@dataclass(frozen=True)
class WorksheetPlan:
    """一次智能组卷的结果。"""

    title: str
    items: tuple[PlanItem, ...]
    limit: int
    notes: tuple[str, ...] = ()
    weak_kcs: tuple[str, ...] = ()
    due_count: int = 0
    transfer_count: int = 0
    transfer_missing: bool = False
    fallback_used: bool = False
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def count(self) -> int:
        """题目数量。"""
        return len(self.items)
