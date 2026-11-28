"""学习路径：卡片状态、课程进度与推荐顺序。"""
from datetime import datetime, timezone

from mathcoach.domain.models import (
    Difficulty,
    ErrorType,
    Exercise,
    ExerciseKind,
    Independence,
    KnowledgeCard,
    MistakeEntry,
    Receipt,
    ReviewState,
    Stage,
)
from mathcoach.memory.path import (
    STATUS_DONE,
    STATUS_LEARNING,
    STATUS_NOT_STARTED,
    STATUS_REVIEW,
    build_learning_path,
)

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


def _exercise(card_id: str, index: int) -> Exercise:
    """构造指定卡片的练习。"""
    return Exercise(
        id=f"{card_id}-e{index}",
        card_id=card_id,
        kind=ExerciseKind.CHOICE,
        stem="题干",
        answer="A",
        solution_outline="思路",
        options=("A", "B"),
    )


def _card(card_id: str, course: str) -> KnowledgeCard:
    """构造含两道练习的卡片。"""
    return KnowledgeCard(
        id=card_id,
        name=f"卡片{card_id}",
        stage=Stage.HIGH_SCHOOL,
        course=course,
        chapter="章",
        difficulty=Difficulty.BASIC,
        intuition="",
        definition="",
        mistakes=(),
        example="",
        exercises=(_exercise(card_id, 1), _exercise(card_id, 2)),
        source="智能体生成",
    )


def _receipt(exercise_id: str) -> Receipt:
    """按练习号推导卡片号并构造收据。"""
    card_id = exercise_id.rsplit("-e", 1)[0]
    return Receipt(
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=10,
        max_hint_level=1,
        goal="练",
        independence=Independence.INDEPENDENT,
        created_at=NOW,
        exercise_id=exercise_id,
    )


def _mistake(card_id: str, exercise_id: str) -> MistakeEntry:
    """构造指定卡片的错题。"""
    return MistakeEntry(
        id=f"m-{exercise_id}",
        exercise_id=exercise_id,
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错",
        correct_answer="A",
        error_type=ErrorType.CONCEPT,
        max_hint_level=1,
        created_at=NOW,
        review_state=ReviewState.UNREVIEWED,
    )


def test_path_marks_learning_review_and_done():
    """学习路径标记复习中、已完成与推荐卡。"""
    cards = [_card("c1", "函数与导数"), _card("c2", "函数与导数")]
    receipts = [
        _receipt("c1-e1"),
        _receipt("c2-e1"),
        _receipt("c2-e2"),
    ]
    mistakes = [_mistake("c1", "c1-e1")]

    path = build_learning_path(cards, receipts, mistakes)
    c1 = path.courses[0].cards[0]
    c2 = path.courses[0].cards[1]
    assert c1.status == STATUS_REVIEW
    assert c1.completed_exercises == 1
    assert c2.status == STATUS_DONE
    assert path.recommended_card is not None
    assert path.recommended_card.id == "c1"
    assert "错题" in path.recommended_reason


def test_path_recommends_learning_before_not_started():
    """推荐优先选学习中的卡片。"""
    cards = [_card("c1", "函数与导数"), _card("c2", "函数与导数")]
    path = build_learning_path(cards, [_receipt("c1-e1")], [])

    assert path.courses[0].cards[0].status == STATUS_LEARNING
    assert path.courses[0].cards[1].status == STATUS_NOT_STARTED
    assert path.recommended_card is not None
    assert path.recommended_card.id == "c1"


def test_path_all_done():
    """全部完成后无推荐并说明原因。"""
    cards = [_card("c1", "函数与导数")]
    path = build_learning_path(
        cards, [_receipt("c1-e1"), _receipt("c1-e2")], []
    )
    assert path.courses[0].completed_cards == 1
    assert path.recommended_card is None
    assert "全部卡片已完成" in path.recommended_reason
