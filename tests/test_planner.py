"""智能练习册：配额、迁移题、薄弱 KC、确定性回退与渲染。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.models import (
    Difficulty,
    ErrorType,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    MistakeEntry,
    ReviewItem,
    ReviewState,
    Stage,
)
from mathcoach.planner import build_plan, plan_to_worksheet, render_plan_markdown
from mathcoach.planner.models import PlanReason
from mathcoach.recall.similar import RecallResult, SimilarCandidate

NOW = datetime(2026, 11, 28, 9, 0, tzinfo=timezone.utc)
KC_MAP = {
    "a-e1": ("kc-x-f1",),
    "a-e2": ("kc-x-f1",),
    "a-e3": ("kc-x-f1",),
    "a-e4": ("kc-x-f1",),
    "b-e1": ("kc-y-f1",),
    "b-e2": ("kc-y-f1",),
    "b-e3": ("kc-y-f1",),
    "b-e4": ("kc-y-f1",),
}


def _exercise(identifier: str, card_id: str) -> Exercise:
    """构造一道最小填空题。"""
    return Exercise(
        id=identifier,
        card_id=card_id,
        kind=ExerciseKind.FILL,
        stem=f"{identifier} 的题干",
        answer="1",
        solution_outline="思路",
    )


def _card(identifier: str, prefix: str, course: str) -> KnowledgeCard:
    """构造一张最小知识点卡。"""
    return KnowledgeCard(
        id=identifier,
        name=identifier,
        stage=Stage.HIGH_SCHOOL,
        course=course,
        chapter="三角",
        difficulty=Difficulty.BASIC,
        intuition="直觉",
        definition="定义",
        mistakes=(),
        example="例子",
        exercises=tuple(
            _exercise(f"{prefix}-e{index}", identifier)
            for index in range(1, 5)
        ),
        source="",
    )


CARD_A = _card("card-a", "a", "代数")
CARD_B = _card("card-b", "b", "几何")
CARDS = (CARD_A, CARD_B)


class _Repo:
    """只实现规划器需要的只读查询。"""

    def __init__(
        self,
        *,
        mistakes=(),
        review_items=(),
        mastery=None,
    ) -> None:
        self._mistakes = list(mistakes)
        self._review_items = list(review_items)
        self._mastery = mastery or {}

    def list_mistakes(self, limit=None, include_mastered=True):
        return self._mistakes[:limit] if limit else self._mistakes

    def list_review_items(self):
        return self._review_items

    def get_mastery(self, card_id: str):
        return self._mastery.get(card_id)


def _mistake(exercise_id: str, card_id: str) -> MistakeEntry:
    """构造一条错题记录。"""
    return MistakeEntry(
        id=f"m-{exercise_id}",
        exercise_id=exercise_id,
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="代数",
        exercise_type=ExerciseKind.FILL,
        stem="题干",
        user_answer="0",
        correct_answer="1",
        error_type=ErrorType.CALCULATION,
        max_hint_level=2,
        created_at=NOW,
        review_state=ReviewState.REVIEWING,
    )


def test_plan_respects_limit_and_deduplicates() -> None:
    """题量受限、不重复，且每条都有理由。"""
    plan = build_plan(
        CARDS,
        repository=_Repo(),
        limit=6,
        kc_mastery={"kc-x-f1": 0.2, "kc-y-f1": 0.8},
        kc_map=KC_MAP,
        now=NOW,
    )

    ids = [item.exercise.id for item in plan.items]
    assert plan.count == 6
    assert len(set(ids)) == 6
    assert all(item.reason_text for item in plan.items)
    assert plan.items[0].card.id == "card-a"


def test_transfer_quota_is_filled(monkeypatch) -> None:
    """有迁移候选时至少选入 1 道迁移题。"""
    source = _mistake("a-e1", "card-a")
    transfer = SimilarCandidate(
        exercise=CARD_A.exercises[2],
        card=CARD_A,
        score=1.0,
        reasons=("same_kc",),
        is_transfer=True,
    )

    def fake_recall(query, cards, *, kc_map, limit):
        return RecallResult(
            candidates=(transfer,),
            fallback_used=False,
            transfer_missing=False,
        )

    monkeypatch.setattr(
        "mathcoach.planner.selector.recall_similar", fake_recall
    )
    plan = build_plan(
        CARDS,
        repository=_Repo(
            mistakes=[source],
            review_items=[ReviewItem(source, NOW - timedelta(days=1))],
        ),
        limit=6,
        kc_mastery={"kc-x-f1": 0.2, "kc-y-f1": 0.8},
        kc_map=KC_MAP,
        now=NOW,
    )

    assert plan.transfer_count >= 1
    assert any(item.is_transfer for item in plan.items)
    assert any(
        PlanReason.TRANSFER in item.reason_codes for item in plan.items
    )


def test_due_review_is_selected_with_reason() -> None:
    """到期题进入计划并标记到期复习。"""
    due = ReviewItem(_mistake("a-e2", "card-a"), NOW - timedelta(hours=1))
    plan = build_plan(
        CARDS,
        repository=_Repo(review_items=[due]),
        limit=6,
        kc_mastery={"kc-x-f1": 0.5, "kc-y-f1": 0.7},
        kc_map=KC_MAP,
        now=NOW,
    )

    due_ids = {
        item.exercise.id
        for item in plan.items
        if PlanReason.DUE_REVIEW in item.reason_codes
    }
    assert "a-e2" in due_ids
    assert plan.due_count >= 1


def test_no_signals_falls_back_to_existing_worksheet() -> None:
    """没有掌握度、错题与到期项时回退到现有练习单来源。"""
    plan = build_plan(
        CARDS,
        repository=_Repo(),
        limit=5,
        current_card_id="card-b",
        kc_map=KC_MAP,
        now=NOW,
    )

    assert plan.fallback_used is True
    assert plan.count == 5
    assert all(
        item.reason_codes == (PlanReason.FALLBACK,)
        for item in plan.items
    )


def test_plan_is_deterministic() -> None:
    """相同输入产生相同题目顺序。"""
    kwargs = dict(
        repository=_Repo(),
        limit=6,
        kc_mastery={"kc-x-f1": 0.2, "kc-y-f1": 0.8},
        kc_map=KC_MAP,
        now=NOW,
    )

    first = build_plan(CARDS, **kwargs)
    second = build_plan(CARDS, **kwargs)

    assert [item.exercise.id for item in first.items] == [
        item.exercise.id for item in second.items
    ]


def test_plan_to_worksheet_and_markdown() -> None:
    """计划可映射为练习单，Markdown 含选题理由。"""
    plan = build_plan(
        CARDS,
        repository=_Repo(),
        limit=4,
        kc_mastery={"kc-x-f1": 0.2, "kc-y-f1": 0.8},
        kc_map=KC_MAP,
        now=NOW,
    )

    worksheet = plan_to_worksheet(plan)
    markdown = render_plan_markdown(plan)

    assert worksheet.count == plan.count
    assert worksheet.source_label == "智能组卷"
    assert "## 选题理由" in markdown
    assert "## 题目" in markdown
