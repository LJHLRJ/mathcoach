"""智能复习包：到期错题优先、去重、不足时补齐。"""
from datetime import datetime, timezone

from mathcoach.domain.models import (
    Difficulty,
    ErrorType,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    MistakeEntry,
    Stage,
)
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.memory.review_package import build_review_package

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


def _card(card_id: str, course: str) -> KnowledgeCard:
    exercises = tuple(
        Exercise(
            id=f"{card_id}-e{index}",
            card_id=card_id,
            kind=ExerciseKind.CHOICE,
            stem="题干",
            answer="A",
            solution_outline="思路",
            options=("A", "B"),
        )
        for index in range(1, 4)
    )
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
        exercises=exercises,
        source="智能体生成",
    )


def _mistake(identifier: str, exercise_id: str) -> MistakeEntry:
    return MistakeEntry(
        id=identifier,
        exercise_id=exercise_id,
        card_id="c1",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错",
        correct_answer="A",
        error_type=ErrorType.CONCEPT,
        max_hint_level=1,
        created_at=NOW,
    )


def test_package_prioritizes_due_mistakes_and_fills_to_five():
    cards = [_card("c1", "函数与导数"), _card("c2", "高等数学")]
    repository = InMemoryRepository()
    repository.save_mistake(_mistake("m1", "c1-e1"))
    repository.save_mistake(_mistake("m2", "c2-e1"))

    package = build_review_package(repository, cards, NOW, count=5)

    assert len(package.questions) == 5
    assert len({item.exercise.id for item in package.questions}) == 5
    assert {item.exercise.id for item in package.questions[:2]} == {
        "c1-e1",
        "c2-e1",
    }
    assert "待复习错题" in package.reason


def test_package_without_mistakes_is_empty():
    package = build_review_package(
        InMemoryRepository(), [_card("c1", "函数与导数")], NOW
    )
    assert package.questions == ()
    assert "暂无待复习错题" in package.reason


def test_due_items_come_before_future_items():
    cards = [_card("c1", "函数与导数"), _card("c2", "高等数学")]
    repository = InMemoryRepository()
    repository.save_mistake(_mistake("m1", "c1-e1"))
    repository.save_mistake(_mistake("m2", "c2-e1"))
    repository.record_review("c1-e1", True, NOW)

    package = build_review_package(repository, cards, NOW, count=5)
    assert package.questions[0].exercise.id == "c2-e1"
