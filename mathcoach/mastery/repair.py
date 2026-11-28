"""前置修复建议：只读计划，不写 FSRS 队列或正式 BKT。"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..domain.models import KnowledgeCard, MistakeEntry
from ..tutor.catalog import EXERCISE_KC, KC_BY_ID
from ..tutor.kc_graph import KC_GRAPH, KCGraph
from .kc_view import kc_card_ids

DEFAULT_THRESHOLD = 0.5
DEFAULT_MIN_SAMPLES = 2
DEFAULT_CONFIDENCE = 0.7
DEFAULT_LIMIT = 3
MISTAKE_WINDOW_DAYS = 30


@dataclass(frozen=True)
class RepairItem:
    """一条前置修复建议。"""

    dependent_kc_id: str
    dependent_name: str
    prerequisite_kc_id: str
    prerequisite_name: str
    dependent_probability: float
    prerequisite_probability: float
    dependent_card_id: str | None
    prerequisite_card_id: str | None
    sample_size: int
    confidence: float
    strength: str
    reason: str
    priority: float


@dataclass(frozen=True)
class RepairPlan:
    """一次前置修复规划。"""

    items: tuple[RepairItem, ...] = ()
    notes: tuple[str, ...] = ()


def _count_recent_mistakes(
    mistakes: Sequence[MistakeEntry],
    kc_map: Mapping[str, Sequence[str]],
    now: datetime,
) -> Counter[str]:
    """统计近 30 天每个 KC 关联的错题数。"""
    start = now - timedelta(days=MISTAKE_WINDOW_DAYS)
    counts: Counter[str] = Counter()
    for entry in mistakes:
        if entry.created_at < start:
            continue
        for kc_id in kc_map.get(entry.exercise_id, ()):
            counts[kc_id] += 1
    return counts


def build_repair_plan(
    cards: Sequence[KnowledgeCard],
    kc_mastery: Mapping[str, float] | None,
    *,
    sample_sizes: Mapping[str, int] | None = None,
    graph: KCGraph = KC_GRAPH,
    mistakes: Sequence[MistakeEntry] = (),
    kc_map: Mapping[str, Sequence[str]] = EXERCISE_KC,
    threshold: float = DEFAULT_THRESHOLD,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    confidence_floor: float = DEFAULT_CONFIDENCE,
    limit: int = DEFAULT_LIMIT,
    now: datetime | None = None,
) -> RepairPlan:
    """按 KC 影子掌握度与前置边生成修复建议。

    只读：不修改错题、FSRS 队列或 BKT；建议卡由调用方决定是否展示。
    """
    moment = now or datetime.now(timezone.utc)
    sizes = sample_sizes or {}
    if not kc_mastery:
        return RepairPlan((), ("尚无 KC 影子掌握度，无法生成前置修复建议。",))
    card_ids = kc_card_ids(cards, kc_map)
    mistake_counts = _count_recent_mistakes(mistakes, kc_map, moment)
    items: dict[tuple[str, str], RepairItem] = {}
    notes: list[str] = []
    missing_prereq = 0

    for dependent_kc, probability in kc_mastery.items():
        if dependent_kc not in KC_BY_ID:
            continue
        if probability >= threshold:
            continue
        sample_size = int(sizes.get(dependent_kc, 0))
        if sample_size < min_samples:
            continue
        edges = graph.prerequisites_of(dependent_kc)
        if not edges:
            continue
        dependent_name = KC_BY_ID[dependent_kc].name
        dependent_card = next(iter(card_ids.get(dependent_kc, ())), None)
        for edge in edges:
            if edge.confidence < confidence_floor:
                continue
            prerequisite_probability = kc_mastery.get(edge.from_kc)
            if prerequisite_probability is None:
                missing_prereq += 1
                continue
            if prerequisite_probability >= threshold:
                continue
            prerequisite_name = KC_BY_ID[edge.from_kc].name
            prerequisite_card = next(
                iter(card_ids.get(edge.from_kc, ())), None
            )
            priority = (
                0.6 * (threshold - probability)
                + 0.4 * (threshold - prerequisite_probability)
                + 0.05 * min(mistake_counts[dependent_kc], 2)
                + (0.05 if edge.strength == "required" else 0.0)
            )
            reason = (
                f"「{dependent_name}」掌握度 {probability:.0%}，"
                f"先修「{prerequisite_name}」仅 "
                f"{prerequisite_probability:.0%}；"
                f"建议先回练 {prerequisite_name}。"
            )
            item = RepairItem(
                dependent_kc_id=dependent_kc,
                dependent_name=dependent_name,
                prerequisite_kc_id=edge.from_kc,
                prerequisite_name=prerequisite_name,
                dependent_probability=probability,
                prerequisite_probability=prerequisite_probability,
                dependent_card_id=dependent_card,
                prerequisite_card_id=prerequisite_card,
                sample_size=sample_size,
                confidence=edge.confidence,
                strength=edge.strength,
                reason=reason,
                priority=round(priority, 4),
            )
            key = (edge.from_kc, dependent_kc)
            if key not in items or item.priority > items[key].priority:
                items[key] = item

    if missing_prereq:
        notes.append("部分薄弱 KC 的先修缺少观测，暂不生成建议。")
    ordered = sorted(
        items.values(),
        key=lambda item: (-item.priority, item.dependent_kc_id),
    )
    if not ordered and not notes:
        notes.append("当前没有满足阈值的前置缺口。")
    return RepairPlan(tuple(ordered[: max(0, int(limit))]), tuple(notes))
