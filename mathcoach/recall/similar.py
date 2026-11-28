"""规则召回：按 KC、错因与题干结构从题库中找相似题。

不引入向量库，不调用模型；只读内容与知识树，不写学习档案。
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..domain.models import (
    ErrorType,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    MistakeEntry,
)
from ..domain.knowledge_tree import KnowledgeTree
from ..tutor.catalog import EXERCISE_KC

DEFAULT_LIMIT = 5
MAX_LIMIT = 5
MIN_LIMIT = 3
_TRANSFER_SURFACE_MAX = 0.85
_MIN_SURFACE = 0.2
_CJK = re.compile(r"[\u4e00-\u9fff]+")
_ALNUM = re.compile(r"[a-z0-9]+")
_MATH = re.compile(r"[a-z]+|\d+(?:\.\d+)?|[-+*/=<>≤≥^]")

_PREFERRED_KINDS: dict[ErrorType, tuple[ExerciseKind, ...]] = {
    ErrorType.CONCEPT: (ExerciseKind.TRUEFALSE, ExerciseKind.CHOICE),
    ErrorType.FORMULA: (
        ExerciseKind.FILL,
        ExerciseKind.EXPR,
        ExerciseKind.CHOICE,
    ),
    ErrorType.CALCULATION: (ExerciseKind.FILL, ExerciseKind.EXPR),
    ErrorType.READING: (
        ExerciseKind.MULTI,
        ExerciseKind.MATCH,
        ExerciseKind.FIND_ERROR,
    ),
    ErrorType.STEP_JUMP: (
        ExerciseKind.PROOF_ORDER,
        ExerciseKind.FIND_ERROR,
    ),
}


@dataclass(frozen=True)
class RecallQuery:
    """一次相似题召回的输入。"""

    exercise: Exercise
    card_id: str
    error_type: ErrorType | None = None
    completed_exercise_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SimilarCandidate:
    """一条召回结果。"""

    exercise: Exercise
    card: KnowledgeCard
    score: float
    reasons: tuple[str, ...]
    is_transfer: bool


@dataclass(frozen=True)
class RecallResult:
    """召回结果与降级标记。"""

    candidates: tuple[SimilarCandidate, ...]
    fallback_used: bool
    transfer_missing: bool
    notes: tuple[str, ...] = ()


def find_exercise(
    cards: Sequence[KnowledgeCard], exercise_id: str
) -> Exercise | None:
    """在题库中按 ID 找题。"""
    for card in cards:
        for exercise in card.exercises:
            if exercise.id == exercise_id:
                return exercise
    return None


def query_from_mistake(
    entry: MistakeEntry, cards: Sequence[KnowledgeCard]
) -> RecallQuery:
    """把错题记录转成召回输入；旧数据缺题时用快照补齐。"""
    exercise = find_exercise(cards, entry.exercise_id)
    if exercise is None:
        snapshot = entry.exercise_snapshot
        exercise = Exercise(
            id=entry.exercise_id,
            card_id=entry.card_id,
            kind=entry.exercise_type,
            stem=entry.stem,
            answer=entry.correct_answer,
            solution_outline=str(snapshot.get("solution_outline") or ""),
            options=tuple(snapshot.get("options") or ()),
            variants=tuple(snapshot.get("variants") or ()),
        )
    return RecallQuery(
        exercise=exercise,
        card_id=entry.card_id,
        error_type=entry.error_type,
    )


def _features(text: str) -> set[str]:
    """提取中文二字片段、字母数字词与数学 token。"""
    normalized = unicodedata.normalize("NFKC", text).lower()
    fragments: set[str] = set()
    for run in _CJK.findall(normalized):
        fragments.update(
            run[index : index + 2] for index in range(len(run) - 1)
        )
    fragments.update(_ALNUM.findall(normalized))
    fragments.update(_MATH.findall(normalized))
    return fragments


def stem_similarity(left: str, right: str) -> float:
    """题干特征 Jaccard 相似度，范围 0–1。"""
    a, b = _features(left), _features(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _kc_ids(
    exercise_id: str,
    card_id: str,
    kc_map: Mapping[str, Sequence[str]],
) -> set[str]:
    """取题目的 KC 集合；没有细粒度 KC 时回退到卡片级。"""
    mapped = kc_map.get(exercise_id)
    if mapped:
        return set(mapped)
    return {f"card:{card_id}"}


def _schema(
    exercise: Exercise,
    tree: KnowledgeTree | None,
    card_id: str,
) -> str:
    """取题目结构标识；知识树缺失时用卡片与题型拼接。"""
    if tree is not None:
        binding = tree.problem_for(exercise.id)
        if binding is not None:
            return binding.problem_schema
    return f"{card_id}:{exercise.kind.value}"


def _score_candidate(
    query: RecallQuery,
    source_card: KnowledgeCard | None,
    card: KnowledgeCard,
    exercise: Exercise,
    *,
    kc_map: Mapping[str, Sequence[str]],
    tree: KnowledgeTree | None,
) -> SimilarCandidate | None:
    """按确定性特征给一道题打分；无任何相似信号时返回 None。"""
    query_kcs = _kc_ids(query.exercise.id, query.card_id, kc_map)
    candidate_kcs = _kc_ids(exercise.id, card.id, kc_map)
    shared = bool(query_kcs & candidate_kcs)
    same_card = card.id == query.card_id
    same_kind = exercise.kind is query.exercise.kind
    query_schema = _schema(query.exercise, tree, query.card_id)
    candidate_schema = _schema(exercise, tree, card.id)
    same_schema = query_schema == candidate_schema
    surface = stem_similarity(query.exercise.stem, exercise.stem)
    preferred = (
        query.error_type is not None
        and exercise.kind in _PREFERRED_KINDS.get(query.error_type, ())
    )
    same_course = (
        source_card is not None
        and card.stage is source_card.stage
        and card.course == source_card.course
    )
    same_chapter = (
        same_course
        and source_card is not None
        and card.chapter == source_card.chapter
    )
    if not (
        same_card
        or shared
        or same_chapter
        or same_course
        or surface >= _MIN_SURFACE
    ):
        return None

    score = 0.0
    reasons: list[str] = []
    if same_card:
        score += 5.0
        reasons.append("同知识点")
    if shared:
        score += 4.0
        reasons.append("共享 KC")
    if same_schema:
        score += 3.0
        reasons.append("同题目结构")
    if same_kind:
        score += 2.0
        reasons.append("同题型")
    if preferred:
        score += 2.0
        reasons.append("匹配错因")
    if same_chapter and not same_card:
        score += 2.0
        reasons.append("同章节")
    elif same_course and not same_card:
        score += 1.0
        reasons.append("同课程")
    if surface > 0:
        score += 2.0 * surface
        reasons.append(f"题干相似 {surface:.0%}")

    related = same_card or shared or same_chapter
    is_transfer = (
        related
        and (not same_card or not same_kind)
        and surface < _TRANSFER_SURFACE_MAX
    )
    if is_transfer:
        reasons.append("结构迁移")
    return SimilarCandidate(
        exercise=exercise,
        card=card,
        score=score,
        reasons=tuple(reasons),
        is_transfer=is_transfer,
    )


def _dedupe(
    candidates: Sequence[SimilarCandidate],
) -> list[SimilarCandidate]:
    """按题目 ID 与归一化题干去重，保留分数更高的一条。"""
    by_id: dict[str, SimilarCandidate] = {}
    for item in candidates:
        current = by_id.get(item.exercise.id)
        if current is None or item.score > current.score:
            by_id[item.exercise.id] = item
    unique: list[SimilarCandidate] = []
    seen_stems: set[str] = set()
    for item in sorted(
        by_id.values(), key=lambda candidate: (-candidate.score, candidate.exercise.id)
    ):
        stem = unicodedata.normalize(
            "NFKC", item.exercise.stem
        ).strip().lower()
        key = stem or f"id:{item.exercise.id}"
        if key in seen_stems:
            continue
        seen_stems.add(key)
        unique.append(item)
    return unique


def _select(
    candidates: Sequence[SimilarCandidate], limit: int
) -> list[SimilarCandidate]:
    """去重后取前 N 条，并尽量保证至少一条结构迁移题。"""
    ranked = _dedupe(candidates)
    selected = ranked[:limit]
    transfer = [item for item in ranked if item.is_transfer]
    if transfer and not any(item.is_transfer for item in selected):
        if selected:
            selected[-1] = transfer[0]
        else:
            selected = transfer[:limit]
    return selected


def _fallback(
    query: RecallQuery,
    cards: Sequence[KnowledgeCard],
    *,
    source_card: KnowledgeCard | None,
    kc_map: Mapping[str, Sequence[str]],
    tree: KnowledgeTree | None,
    limit: int,
) -> list[SimilarCandidate]:
    """召回为空时推荐同 KC/同卡的未做题。"""
    query_kcs = _kc_ids(query.exercise.id, query.card_id, kc_map)
    candidates: list[SimilarCandidate] = []
    for card in cards:
        for exercise in card.exercises:
            if exercise.id == query.exercise.id:
                continue
            if exercise.id in query.completed_exercise_ids:
                continue
            shared = bool(
                query_kcs
                & _kc_ids(exercise.id, card.id, kc_map)
            )
            if card.id != query.card_id and not shared:
                continue
            candidate = _score_candidate(
                query,
                source_card,
                card,
                exercise,
                kc_map=kc_map,
                tree=tree,
            )
            if candidate is not None:
                candidates.append(candidate)
    return _select(candidates, limit)


def recall_similar(
    query: RecallQuery,
    cards: Sequence[KnowledgeCard],
    *,
    tree: KnowledgeTree | None = None,
    kc_map: Mapping[str, Sequence[str]] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> RecallResult:
    """按 KC、错因与题干结构召回相似题。

    Args:
        query: 当前错题与错因。
        cards: 全部知识点卡。
        tree: 知识树，用于题目结构标识。
        kc_map: 题目 ID -> KC ID 集合；缺省使用 ``content/kc`` 目录。
        limit: 返回上限，最多 5 道。

    Returns:
        ``RecallResult``；召回为空时使用同 KC 未做题降级。
    """
    safe_limit = max(MIN_LIMIT, min(MAX_LIMIT, int(limit)))
    mapping = kc_map if kc_map is not None else EXERCISE_KC
    source_card = next(
        (card for card in cards if card.id == query.card_id), None
    )
    scored: list[SimilarCandidate] = []
    for card in cards:
        for exercise in card.exercises:
            if exercise.id == query.exercise.id:
                continue
            candidate = _score_candidate(
                query,
                source_card,
                card,
                exercise,
                kc_map=mapping,
                tree=tree,
            )
            if candidate is not None:
                scored.append(candidate)
    selected = _select(scored, safe_limit)
    if selected:
        transfer_missing = not any(
            item.is_transfer for item in selected
        )
        return RecallResult(
            candidates=tuple(selected),
            fallback_used=False,
            transfer_missing=transfer_missing,
            notes=("transfer_missing",) if transfer_missing else (),
        )
    fallback = _fallback(
        query,
        cards,
        source_card=source_card,
        kc_map=mapping,
        tree=tree,
        limit=safe_limit,
    )
    transfer_missing = not any(
        item.is_transfer for item in fallback
    )
    return RecallResult(
        candidates=tuple(fallback),
        fallback_used=True,
        transfer_missing=transfer_missing,
        notes=(
            ("no_similar", "same_kc_uncompleted")
            if fallback
            else ("no_similar", "no_uncompleted_same_kc")
        ),
    )
