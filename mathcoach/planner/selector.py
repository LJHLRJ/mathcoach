"""智能练习册选题：薄弱 KC、到期复习与迁移题配额。"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from ..domain.models import (
    Exercise,
    KnowledgeCard,
    MistakeEntry,
    ReviewItem,
)
from ..memory.repository import Repository
from ..recall.similar import query_from_mistake, recall_similar
from ..timeutil import end_of_local_day
from ..tutor.catalog import EXERCISE_KC, KC_BY_ID
from ..worksheet import (
    Worksheet,
    WorksheetItem,
    WorksheetSource,
    build_worksheet,
)
from .models import (
    REASON_LABELS,
    PlanItem,
    PlanReason,
    WorksheetPlan,
)

DEFAULT_LIMIT = 10
MAX_LIMIT = 30
TRANSFER_QUOTA = 2
DUE_SHARE = 0.3
WEAK_THRESHOLD = 0.6
INITIAL_MASTERY = 0.3
WEIGHT_WEAKNESS = 0.35
WEIGHT_DUE = 0.25
WEIGHT_ERROR = 0.20
WEIGHT_TRANSFER = 0.10
WEIGHT_COVERAGE = 0.10
PER_CARD_CAP = 2
PER_KC_CAP = 2
_RECALL_SOURCES = 5


@dataclass(frozen=True)
class _Candidate:
    """候选题目及其确定性打分信号。"""

    exercise: Exercise
    card: KnowledgeCard
    kc_ids: tuple[str, ...]
    weakness: float
    due: bool
    due_at: datetime | None
    error_score: float
    transfer: bool

    @property
    def base_score(self) -> float:
        """薄弱、到期、错因与迁移四项的加权分。"""
        return (
            WEIGHT_WEAKNESS * self.weakness
            + WEIGHT_DUE * (1.0 if self.due else 0.0)
            + WEIGHT_ERROR * self.error_score
            + WEIGHT_TRANSFER * (1.0 if self.transfer else 0.0)
        )


def _mastery(value: float | None) -> float | None:
    """读取卡片掌握度；没有记录时返回 None。"""
    return None if value is None else max(0.0, min(1.0, value))


def _due_items(
    repository: Repository, now: datetime
) -> list[ReviewItem]:
    """取今天结束前到期的复习项。"""
    today_end = end_of_local_day(now)
    return [
        item
        for item in repository.list_review_items()
        if item.due_at <= today_end
    ]


def _weak_kcs(
    kc_mastery: Mapping[str, float] | None,
) -> tuple[str, ...]:
    """按掌握度升序返回低于阈值的 KC，最多 6 个。"""
    if not kc_mastery:
        return ()
    weak = sorted(
        (
            (kc_id, probability)
            for kc_id, probability in kc_mastery.items()
            if probability < WEAK_THRESHOLD
        ),
        key=lambda item: (item[1], item[0]),
    )
    return tuple(kc_id for kc_id, _ in weak[:6])


def _transfer_ids(
    due_items: Sequence[ReviewItem],
    mistakes: Sequence[MistakeEntry],
    cards: Sequence[KnowledgeCard],
    kc_map: Mapping[str, Sequence[str]],
) -> tuple[set[str], bool, str]:
    """用相似题召回找结构迁移题；返回题目 ID、是否有来源与提示。"""
    sources: list[MistakeEntry] = [
        item.mistake for item in due_items
    ]
    sources.extend(mistakes)
    if not sources:
        return set(), False, ""
    transfer: set[str] = set()
    seen: set[str] = set()
    for entry in sources:
        if entry.exercise_id in seen:
            continue
        seen.add(entry.exercise_id)
        if len(seen) > _RECALL_SOURCES:
            break
        query_kcs = set(kc_map.get(entry.exercise_id, ()))
        if not query_kcs:
            continue
        try:
            result = recall_similar(
                query_from_mistake(entry, cards),
                cards,
                kc_map=kc_map,
                limit=5,
            )
        except Exception:
            return transfer, True, "相似题召回失败，已跳过迁移题。"
        for candidate in result.candidates:
            if not candidate.is_transfer:
                continue
            candidate_kcs = set(
                kc_map.get(candidate.exercise.id, ())
            )
            if query_kcs & candidate_kcs:
                transfer.add(candidate.exercise.id)
    return transfer, True, ""


def _candidate(
    exercise: Exercise,
    card: KnowledgeCard,
    *,
    kc_map: Mapping[str, Sequence[str]],
    kc_mastery: Mapping[str, float] | None,
    mastery_by_card: Mapping[str, float | None],
    due_by_id: Mapping[str, datetime],
    error_by_card: Counter[str],
    transfer_ids: set[str],
) -> _Candidate:
    """构造一个候选题目。"""
    kc_ids = tuple(kc_map.get(exercise.id, ()))
    if kc_ids and kc_mastery:
        weakness = 1.0 - min(
            kc_mastery.get(kc_id, INITIAL_MASTERY) for kc_id in kc_ids
        )
    else:
        card_mastery = mastery_by_card.get(card.id)
        weakness = 1.0 - (
            card_mastery
            if card_mastery is not None
            else INITIAL_MASTERY
        )
    return _Candidate(
        exercise=exercise,
        card=card,
        kc_ids=kc_ids,
        weakness=max(0.0, min(1.0, weakness)),
        due=exercise.id in due_by_id,
        due_at=due_by_id.get(exercise.id),
        error_score=min(error_by_card[card.id], 3) / 3,
        transfer=exercise.id in transfer_ids,
    )


def _reason_text(
    codes: Sequence[PlanReason], candidate: _Candidate, weak_kcs: set[str]
) -> str:
    """把理由码转成一句中文说明。"""
    labels: list[str] = []
    for code in codes:
        if code is PlanReason.WEAK_KC and candidate.kc_ids:
            weak_id = next(
                (
                    kc_id
                    for kc_id in candidate.kc_ids
                    if kc_id in weak_kcs
                ),
                candidate.kc_ids[0],
            )
            component = KC_BY_ID.get(weak_id)
            name = component.name if component is not None else weak_id
            labels.append(f"{REASON_LABELS[code]}：{name}")
        else:
            labels.append(REASON_LABELS[code])
    return " · ".join(dict.fromkeys(labels))


def _plan_items(
    selected: Sequence[_Candidate],
    *,
    weak_kcs: set[str],
    weak_cards: set[str],
    error_by_card: Counter[str],
) -> tuple[PlanItem, ...]:
    """为选中的题目补写理由。"""
    items: list[PlanItem] = []
    seen_kcs: set[str] = set()
    seen_cards: set[str] = set()
    for candidate in selected:
        codes: list[PlanReason] = []
        if candidate.due:
            codes.append(PlanReason.DUE_REVIEW)
        if candidate.transfer:
            codes.append(PlanReason.TRANSFER)
        if (
            set(candidate.kc_ids) & weak_kcs
            or candidate.card.id in weak_cards
        ):
            codes.append(PlanReason.WEAK_KC)
        if error_by_card[candidate.card.id] > 0:
            codes.append(PlanReason.REPEATED_ERROR)
        new_coverage = (
            bool(set(candidate.kc_ids) - seen_kcs)
            if candidate.kc_ids
            else candidate.card.id not in seen_cards
        )
        if new_coverage:
            codes.append(PlanReason.COVERAGE)
        if not codes:
            codes.append(PlanReason.FALLBACK)
        seen_kcs.update(candidate.kc_ids)
        seen_cards.add(candidate.card.id)
        items.append(
            PlanItem(
                exercise=candidate.exercise,
                card=candidate.card,
                kc_ids=candidate.kc_ids,
                reason_codes=tuple(codes),
                reason_text=_reason_text(codes, candidate, weak_kcs),
                score=round(candidate.base_score, 4),
                is_transfer=candidate.transfer,
            )
        )
    return tuple(items)


def _fallback_plan(
    cards: Sequence[KnowledgeCard],
    repository: Repository,
    *,
    current_card_id: str | None,
    limit: int,
    now: datetime,
    notes: Sequence[str],
) -> WorksheetPlan:
    """没有可用信号时回退到现有练习单来源。"""
    worksheet = build_worksheet(
        cards,
        source=WorksheetSource.SAME_TOPIC,
        repository=repository,
        current_card_id=current_card_id,
        count=limit,
        now=now,
    )
    cards_by_id = {card.id: card for card in cards}
    items: list[PlanItem] = []
    for item in worksheet.items:
        card = item.card or cards_by_id.get(item.exercise.card_id)
        if card is None:
            continue
        items.append(
            PlanItem(
                exercise=item.exercise,
                card=card,
                reason_codes=(PlanReason.FALLBACK,),
                reason_text=REASON_LABELS[PlanReason.FALLBACK],
            )
        )
    if not items:
        for card in cards:
            for exercise in card.exercises:
                items.append(
                    PlanItem(
                        exercise=exercise,
                        card=card,
                        reason_codes=(PlanReason.FALLBACK,),
                        reason_text=REASON_LABELS[PlanReason.FALLBACK],
                    )
                )
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
    elif len(items) < limit:
        seen = {item.exercise.id for item in items}
        for card in cards:
            for exercise in card.exercises:
                if exercise.id in seen:
                    continue
                items.append(
                    PlanItem(
                        exercise=exercise,
                        card=card,
                        reason_codes=(PlanReason.FALLBACK,),
                        reason_text=REASON_LABELS[PlanReason.FALLBACK],
                    )
                )
                seen.add(exercise.id)
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
    return WorksheetPlan(
        title="智能练习册",
        items=tuple(items[:limit]),
        limit=limit,
        notes=tuple(dict.fromkeys((*notes, *worksheet.notes))),
        fallback_used=True,
        generated_at=now,
    )


def build_plan(
    cards: Sequence[KnowledgeCard],
    *,
    repository: Repository,
    limit: int = DEFAULT_LIMIT,
    current_card_id: str | None = None,
    kc_mastery: Mapping[str, float] | None = None,
    kc_map: Mapping[str, Sequence[str]] | None = None,
    now: datetime | None = None,
) -> WorksheetPlan:
    """按薄弱 KC、到期复习与迁移配额生成选题计划。

    Args:
        cards: 全部知识点卡。
        repository: 学习档案；只读调用错题、复习与掌握度查询。
        limit: 题量上限，夹在 1–30。
        current_card_id: 无信号回退时使用的当前卡片。
        kc_mastery: KC 影子掌握度；缺省或为空时回退到卡片掌握度。
        kc_map: 题目 ID -> KC ID 集合；缺省使用 ``content/kc`` 目录。
        now: 生成时间。

    Returns:
        ``WorksheetPlan``；选题理由与配额结果都在计划里。
    """
    safe_limit = max(1, min(MAX_LIMIT, int(limit)))
    moment = now or datetime.now(timezone.utc)
    mapping = kc_map if kc_map is not None else EXERCISE_KC
    notes: list[str] = []

    due_items = _due_items(repository, moment)
    due_by_id = {
        item.mistake.exercise_id: item.due_at
        for item in due_items
    }
    mistakes = repository.list_mistakes(limit=None)
    error_by_card: Counter[str] = Counter(
        entry.card_id for entry in mistakes
    )
    mastery_by_card = {
        card.id: _mastery(repository.get_mastery(card.id))
        for card in cards
    }
    weak_kcs = _weak_kcs(kc_mastery)
    weak_kcs_set = set(weak_kcs)
    weak_cards = {
        card.id
        for card in cards
        if mastery_by_card[card.id] is not None
        and mastery_by_card[card.id] < WEAK_THRESHOLD  # type: ignore[operator]
    }
    if not kc_mastery:
        notes.append("尚无 KC 级掌握度，已回退到卡片掌握度。")

    transfer_ids, has_transfer_sources, recall_note = _transfer_ids(
        due_items, mistakes, cards, mapping
    )
    if recall_note:
        notes.append(recall_note)

    pool = [
        _candidate(
            exercise,
            card,
            kc_map=mapping,
            kc_mastery=kc_mastery,
            mastery_by_card=mastery_by_card,
            due_by_id=due_by_id,
            error_by_card=error_by_card,
            transfer_ids=transfer_ids,
        )
        for card in cards
        for exercise in card.exercises
    ]
    if not pool:
        return WorksheetPlan(
            title="智能练习册",
            items=(),
            limit=safe_limit,
            notes=("题库为空。",),
            generated_at=moment,
        )
    if not weak_kcs_set and not weak_cards and not due_by_id and not transfer_ids:
        return _fallback_plan(
            cards,
            repository,
            current_card_id=current_card_id,
            limit=safe_limit,
            now=moment,
            notes=notes,
        )

    cards_by_id = {card.id: card for card in cards}
    focus_card = cards_by_id.get(current_card_id) if current_card_id else None
    if focus_card is None and weak_kcs:
        weak_id = weak_kcs[0]
        focus_card = next(
            (
                card
                for card in cards
                if any(
                    weak_id in mapping.get(exercise.id, ())
                    for exercise in card.exercises
                )
            ),
            None,
        )

    def affinity(candidate: _Candidate) -> int:
        """同课程候选在分数相同时优先。"""
        if focus_card is None:
            return 0
        return int(
            candidate.card.stage is focus_card.stage
            and candidate.card.course == focus_card.course
        )

    selected: list[_Candidate] = []
    selected_ids: set[str] = set()
    card_counts: Counter[str] = Counter()
    kc_counts: Counter[str] = Counter()
    covered_kcs: set[str] = set()
    covered_cards: set[str] = set()

    def take(candidate: _Candidate, *, enforce_caps: bool = True) -> bool:
        """按配额加入一道题；重复或超限时返回 False。"""
        identifier = candidate.exercise.id
        if identifier in selected_ids:
            return False
        if enforce_caps:
            if card_counts[candidate.card.id] >= PER_CARD_CAP:
                return False
            if any(
                kc_counts[kc_id] >= PER_KC_CAP
                for kc_id in candidate.kc_ids
            ):
                return False
        selected.append(candidate)
        selected_ids.add(identifier)
        card_counts[candidate.card.id] += 1
        for kc_id in candidate.kc_ids:
            kc_counts[kc_id] += 1
        covered_kcs.update(candidate.kc_ids)
        covered_cards.add(candidate.card.id)
        return True

    transfer_quota = TRANSFER_QUOTA if safe_limit >= 6 else 1
    transfer_taken = 0
    for candidate in sorted(
        (item for item in pool if item.transfer),
        key=lambda item: (-item.base_score, item.exercise.id),
    ):
        if transfer_taken >= transfer_quota:
            break
        if take(candidate):
            transfer_taken += 1

    due_quota = min(
        len(due_by_id), max(1, math.ceil(safe_limit * DUE_SHARE))
    )
    due_taken = 0
    for candidate in sorted(
        (item for item in pool if item.due),
        key=lambda item: (
            item.due_at or datetime.max.replace(tzinfo=timezone.utc),
            -item.base_score,
            item.exercise.id,
        ),
    ):
        if due_taken >= due_quota:
            break
        if take(candidate):
            due_taken += 1

    while len(selected) < safe_limit:
        best: _Candidate | None = None
        best_key = (-1.0, -1)
        for candidate in pool:
            if candidate.exercise.id in selected_ids:
                continue
            if card_counts[candidate.card.id] >= PER_CARD_CAP:
                continue
            if any(
                kc_counts[kc_id] >= PER_KC_CAP
                for kc_id in candidate.kc_ids
            ):
                continue
            new_coverage = (
                bool(set(candidate.kc_ids) - covered_kcs)
                if candidate.kc_ids
                else candidate.card.id not in covered_cards
            )
            score = candidate.base_score + (
                WEIGHT_COVERAGE if new_coverage else 0.0
            )
            key = (score, affinity(candidate))
            if key > best_key or (
                key == best_key
                and (best is None or candidate.exercise.id < best.exercise.id)
            ):
                best = candidate
                best_key = key
        if best is None:
            break
        take(best)

    if len(selected) < safe_limit:
        for candidate in sorted(
            pool,
            key=lambda item: (
                -item.base_score,
                -affinity(item),
                item.exercise.id,
            ),
        ):
            if len(selected) >= safe_limit:
                break
            if candidate.exercise.id not in selected_ids:
                take(candidate, enforce_caps=False)

    if transfer_taken == 0 and has_transfer_sources:
        notes.append("本册未包含结构迁移题。")

    items = _plan_items(
        selected,
        weak_kcs=weak_kcs_set,
        weak_cards=weak_cards,
        error_by_card=error_by_card,
    )
    if not items:
        return _fallback_plan(
            cards,
            repository,
            current_card_id=current_card_id,
            limit=safe_limit,
            now=moment,
            notes=notes,
        )
    return WorksheetPlan(
        title="智能练习册",
        items=items,
        limit=safe_limit,
        notes=tuple(dict.fromkeys(notes)),
        weak_kcs=weak_kcs,
        due_count=sum(1 for item in selected if item.due),
        transfer_count=transfer_taken,
        transfer_missing=transfer_taken == 0,
        generated_at=moment,
    )
