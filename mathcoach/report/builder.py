"""可解释报告的确定性构建：统计层结论 + 记录 ID 证据。"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone

from ..domain.models import (
    ErrorType,
    Independence,
    MistakeEntry,
    Receipt,
)
from ..memory.repository import Repository
from ..timeutil import end_of_local_day
from ..tutor.catalog import EXERCISE_KC, KC_BY_ID
from .models import (
    EvidenceAnchor,
    ExplainableReport,
    ReportConclusion,
    ReportMetric,
)

WINDOW_DAYS = 7
WEAK_THRESHOLD = 0.6
MAX_CONCLUSIONS = 3
MAX_EVIDENCE = 3


def _anchor_from_mistake(entry: MistakeEntry) -> EvidenceAnchor:
    """把错题记录转成证据锚点。"""
    return EvidenceAnchor(
        kind="mistake",
        id=entry.id,
        exercise_id=entry.exercise_id,
        card_id=entry.card_id,
        occurred_at=entry.created_at,
        snippet=(
            f"作答 {entry.user_answer or '空'} → "
            f"正确答案 {entry.correct_answer}"
            f"（{entry.error_type.value}）"
        ),
    )


def _anchor_from_receipt(receipt: Receipt) -> EvidenceAnchor:
    """把收据转成证据锚点。"""
    return EvidenceAnchor(
        kind="receipt",
        id=receipt.id,
        exercise_id=receipt.exercise_id,
        card_id=receipt.card_id,
        occurred_at=receipt.created_at,
        snippet=(
            f"{receipt.exercise_type.value} · L{receipt.max_hint_level}"
            f" · {receipt.duration_s}s"
        ),
    )


def _confidence(evidence: Sequence[EvidenceAnchor]) -> str:
    """按证据数量给出置信度。"""
    if len(evidence) >= 2:
        return "high"
    if evidence:
        return "medium"
    return "low"


def _weak_kc_conclusion(
    mistakes: Sequence[MistakeEntry],
    receipts: Sequence[Receipt],
    kc_mastery: Mapping[str, float] | None,
) -> ReportConclusion | None:
    """找出最薄弱 KC，并用相关作答做证据。"""
    if not kc_mastery:
        return None
    weak = sorted(
        (
            (kc_id, probability)
            for kc_id, probability in kc_mastery.items()
            if probability < WEAK_THRESHOLD
        ),
        key=lambda item: (item[1], item[0]),
    )
    if not weak:
        return None
    kc_id, probability = weak[0]
    component = KC_BY_ID.get(kc_id)
    name = component.name if component is not None else kc_id
    related = {
        exercise_id
        for exercise_id, kc_ids in EXERCISE_KC.items()
        if kc_id in kc_ids
    }
    evidence = [
        _anchor_from_mistake(entry)
        for entry in mistakes
        if entry.exercise_id in related
    ][:MAX_EVIDENCE]
    if not evidence:
        evidence = [
            _anchor_from_receipt(receipt)
            for receipt in receipts
            if receipt.exercise_id in related
        ][:MAX_EVIDENCE]
    gaps: tuple[str, ...] = ()
    if not evidence:
        gaps = ("该 KC 近 7 天没有作答记录，结论仅来自掌握度。",)
    return ReportConclusion(
        id=f"weak-kc:{kc_id}",
        kind="weak_kc",
        statement=(
            f"「{name}」当前掌握度 {probability:.0%}，"
            "是近 7 天最需要优先补强的知识点。"
        ),
        metrics=(
            ReportMetric(
                "kc.mastery", probability, "概率", f"{name}掌握度"
            ),
        ),
        evidence=tuple(evidence),
        confidence=_confidence(evidence),
        data_gaps=gaps,
    )


def _weak_card_conclusion(
    repository: Repository,
    mistakes: Sequence[MistakeEntry],
    receipts: Sequence[Receipt],
) -> ReportConclusion | None:
    """没有 KC 数据时，退到卡片级最薄弱项。"""
    card_ids = {
        entry.card_id for entry in mistakes
    } | {receipt.card_id for receipt in receipts}
    scored = [
        (card_id, repository.get_mastery(card_id))
        for card_id in sorted(card_ids)
    ]
    scored = [
        (card_id, value)
        for card_id, value in scored
        if value is not None
    ]
    if not scored:
        return None
    card_id, probability = min(scored, key=lambda item: item[1])
    evidence = [
        _anchor_from_mistake(entry)
        for entry in mistakes
        if entry.card_id == card_id
    ][:MAX_EVIDENCE]
    if not evidence:
        evidence = [
            _anchor_from_receipt(receipt)
            for receipt in receipts
            if receipt.card_id == card_id
        ][:MAX_EVIDENCE]
    return ReportConclusion(
        id=f"weak-card:{card_id}",
        kind="weak_card",
        statement=(
            f"卡片「{card_id}」当前掌握度 {probability:.0%}，"
            "是本周最需要优先补强的卡片。"
        ),
        metrics=(
            ReportMetric(
                "card.mastery", probability, "概率", "卡片掌握度"
            ),
        ),
        evidence=tuple(evidence),
        confidence=_confidence(evidence),
    )


def _error_conclusion(
    mistakes: Sequence[MistakeEntry],
) -> ReportConclusion | None:
    """统计本周最高频错因。"""
    if not mistakes:
        return None
    counter = Counter(entry.error_type for entry in mistakes)
    error_type, count = counter.most_common(1)[0]
    share = count / len(mistakes)
    evidence = [
        _anchor_from_mistake(entry)
        for entry in mistakes
        if entry.error_type is error_type
    ][:MAX_EVIDENCE]
    return ReportConclusion(
        id=f"top-error:{error_type.value}",
        kind="error_pattern",
        statement=(
            f"近 7 天新增 {len(mistakes)} 道错题，"
            f"其中「{_error_label(error_type)}」{count} 道"
            f"（{share:.0%}）最多。"
        ),
        metrics=(
            ReportMetric(
                "mistake.count", float(count), "道", "该错因错题数"
            ),
            ReportMetric("mistake.share", share, "比例", "错因占比"),
        ),
        evidence=tuple(evidence),
        confidence=_confidence(evidence),
    )


def _review_conclusion(
    repository: Repository,
    receipts: Sequence[Receipt],
    now: datetime,
) -> ReportConclusion | None:
    """输出到期复习压力；没有到期项时输出独立完成率。"""
    today_end = end_of_local_day(now)
    due = [
        item
        for item in repository.list_review_items()
        if item.due_at <= today_end
    ]
    if due:
        evidence = [
            _anchor_from_mistake(item.mistake) for item in due
        ][:MAX_EVIDENCE]
        return ReportConclusion(
            id="review-load:today",
            kind="review_load",
            statement=f"今天有 {len(due)} 道错题到期复习。",
            metrics=(
                ReportMetric(
                    "review.due", float(len(due)), "道", "今日到期题"
                ),
            ),
            evidence=tuple(evidence),
            confidence=_confidence(evidence),
        )
    if not receipts:
        return None
    independent = sum(
        1
        for receipt in receipts
        if receipt.independence is Independence.INDEPENDENT
    )
    share = independent / len(receipts)
    evidence = [
        _anchor_from_receipt(receipt) for receipt in receipts
    ][:MAX_EVIDENCE]
    return ReportConclusion(
        id="independence:window",
        kind="independence",
        statement=(
            f"近 7 天完成 {len(receipts)} 次作答，"
            f"其中独立完成 {independent} 次（{share:.0%}）。"
        ),
        metrics=(
            ReportMetric(
                "receipt.count", float(len(receipts)), "次", "作答次数"
            ),
            ReportMetric(
                "receipt.independent", share, "比例", "独立完成率"
            ),
        ),
        evidence=tuple(evidence),
        confidence=_confidence(evidence),
    )


def _error_label(error_type: ErrorType) -> str:
    """错因枚举已含中文，直接返回文字。"""
    return error_type.value


def build_explainable_report(
    repository: Repository,
    *,
    now: datetime | None = None,
    window_days: int = WINDOW_DAYS,
    kc_mastery: Mapping[str, float] | None = None,
) -> ExplainableReport:
    """构建确定性的“结论 ↔ 证据”报告。

    Args:
        repository: 学习档案；只读调用收据、错题、复习队列与掌握度。
        now: 窗口结束时间。
        window_days: 统计窗口天数。
        kc_mastery: KC 影子掌握度；为空时退到卡片级掌握度。

    Returns:
        ``ExplainableReport``；证据不足时结论为空并带说明。
    """
    moment = now or datetime.now(timezone.utc)
    start = moment - timedelta(days=max(1, int(window_days)))
    receipts = [
        receipt
        for receipt in repository.list_receipts(limit=None)
        if start <= receipt.created_at <= moment
    ]
    mistakes = [
        entry
        for entry in repository.list_mistakes(limit=None)
        if start <= entry.created_at <= moment
    ]
    conclusions: list[ReportConclusion] = []
    weak = _weak_kc_conclusion(mistakes, receipts, kc_mastery)
    if weak is None:
        weak = _weak_card_conclusion(repository, mistakes, receipts)
    if weak is not None:
        conclusions.append(weak)
    error = _error_conclusion(mistakes)
    if error is not None:
        conclusions.append(error)
    review = _review_conclusion(repository, receipts, moment)
    if review is not None:
        conclusions.append(review)

    notes: list[str] = []
    if not conclusions:
        notes.append("近 7 天证据不足，暂不生成结论。")
    return ExplainableReport(
        start=start,
        end=moment,
        conclusions=tuple(conclusions[:MAX_CONCLUSIONS]),
        notes=tuple(notes),
        generated_at=moment,
    )
