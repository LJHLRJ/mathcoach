"""混合复习包接入：缺口优先、总数 5、无重复。"""
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
from mathcoach.memory.scheduler import build_review_pack

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _card(card_id: str) -> KnowledgeCard:
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
        name=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        chapter="章",
        difficulty=Difficulty.BASIC,
        intuition="",
        definition="",
        mistakes=(),
        example="",
        exercises=exercises,
        source="智能体生成",
    )


def _mistake(identifier: str, card_id: str) -> MistakeEntry:
    return MistakeEntry(
        id=identifier,
        exercise_id=f"{card_id}-e1",
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
    )


def test_review_pack_places_gap_first_and_totals_five():
    cards = [_card("c1"), _card("c2"), _card("c3")]
    repository = InMemoryRepository()
    repository.save_mistake(_mistake("m1", "c1"))

    questions = build_review_pack(
        repository, cards, NOW, priority_card_ids={"c2"}, total=5
    )

    assert len(questions) == 5
    assert questions[0].card.id == "c2"
    assert len({question.exercise.id for question in questions}) == 5


def test_review_pack_has_no_duplicates_when_gap_is_due():
    cards = [_card("c1"), _card("c2")]
    repository = InMemoryRepository()
    repository.save_mistake(_mistake("m1", "c1"))

    questions = build_review_pack(
        repository, cards, NOW, priority_card_ids={"c1"}, total=5
    )

    ids = [question.exercise.id for question in questions]
    assert len(ids) == len(set(ids))
    assert len(ids) == 5
