"""KC 影子掌握度只读视图：推荐与展示共用，不写正式 mastery。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..domain.learning_path import Recommendation
from ..domain.models import KnowledgeCard
from ..tutor.catalog import EXERCISE_KC, KC_BY_ID

WEAK_KC_THRESHOLD = 0.6
MAX_PROGRESS = 10


@dataclass(frozen=True)
class KCProgress:
    """一个 KC 的影子掌握度视图。"""

    kc_id: str
    name: str
    probability: float
    sample_size: int = 0
    card_ids: tuple[str, ...] = ()


def kc_card_ids(
    cards: Sequence[KnowledgeCard],
    kc_map: Mapping[str, Sequence[str]] = EXERCISE_KC,
) -> dict[str, tuple[str, ...]]:
    """反向映射 KC -> 关联卡片 ID。"""
    mapping: dict[str, list[str]] = {}
    for card in cards:
        for exercise in card.exercises:
            for kc_id in kc_map.get(exercise.id, ()):
                card_ids = mapping.setdefault(kc_id, [])
                if card.id not in card_ids:
                    card_ids.append(card.id)
    return {
        kc_id: tuple(card_ids) for kc_id, card_ids in mapping.items()
    }


def build_kc_progress(
    cards: Sequence[KnowledgeCard],
    kc_mastery: Mapping[str, float] | None,
    *,
    sample_sizes: Mapping[str, int] | None = None,
    kc_map: Mapping[str, Sequence[str]] = EXERCISE_KC,
    limit: int = MAX_PROGRESS,
) -> tuple[KCProgress, ...]:
    """把 KC 影子概率整理成按掌握度升序的展示行。"""
    if not kc_mastery:
        return ()
    card_ids = kc_card_ids(cards, kc_map)
    sizes = sample_sizes or {}
    progress = [
        KCProgress(
            kc_id=kc_id,
            name=KC_BY_ID[kc_id].name,
            probability=max(0.0, min(1.0, probability)),
            sample_size=int(sizes.get(kc_id, 0)),
            card_ids=card_ids.get(kc_id, ()),
        )
        for kc_id, probability in kc_mastery.items()
        if kc_id in KC_BY_ID
    ]
    progress.sort(key=lambda item: (item.probability, item.kc_id))
    return tuple(progress[: max(0, int(limit))])


def weak_kc_recommendations(
    cards: Sequence[KnowledgeCard],
    kc_mastery: Mapping[str, float] | None,
    *,
    sample_sizes: Mapping[str, int] | None = None,
    card_mastery: Mapping[str, float] | None = None,
    kc_map: Mapping[str, Sequence[str]] = EXERCISE_KC,
    threshold: float = WEAK_KC_THRESHOLD,
    limit: int = 3,
) -> list[Recommendation]:
    """把低于阈值的 KC 转成卡片级推荐；同一卡片只出现一次。"""
    progress = build_kc_progress(
        cards,
        kc_mastery,
        sample_sizes=sample_sizes,
        kc_map=kc_map,
        limit=MAX_PROGRESS,
    )
    recommendations: list[Recommendation] = []
    seen_cards: set[str] = set()
    for item in progress:
        if item.probability >= threshold:
            continue
        for card_id in item.card_ids:
            if card_id in seen_cards:
                continue
            seen_cards.add(card_id)
            basis = (
                f"KC 影子掌握度 {item.probability:.0%}"
                f"（样本 {item.sample_size}）"
            )
            official = (card_mastery or {}).get(card_id)
            if official is not None:
                basis += f"；卡片 BKT {official:.0%}"
            recommendations.append(
                Recommendation(
                    card_id=card_id,
                    reason=f"薄弱 KC「{item.name}」，建议回练对应卡片",
                    basis=basis,
                )
            )
            break
        if len(recommendations) >= limit:
            break
    return recommendations
