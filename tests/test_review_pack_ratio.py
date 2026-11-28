"""新卡/复习配比：纯组合与复习包接入。"""
from datetime import UTC, datetime

from mathcoach.domain.models import (
    Difficulty,
    Exercise,
    ExerciseKind,
    Independence,
    KnowledgeCard,
    Receipt,
    Stage,
)
from mathcoach.domain.review_pack import compose
from mathcoach.domain.settings import AppSettings
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.memory.review_package import build_review_package
from mathcoach.memory.scheduler import build_review_pack

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def _card(card_id: str) -> KnowledgeCard:
    """构造含三道选择题的卡片。"""
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
        exercises=tuple(
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
        ),
        source="智能体生成",
    )


def _receipt(card_id: str) -> Receipt:
    """构造指定卡片的收据。"""
    return Receipt(
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=12,
        max_hint_level=1,
        goal="复习",
        independence=Independence.INDEPENDENT,
        created_at=NOW,
        exercise_id=f"{card_id}-e1",
    )


def test_default_new_ratio_is_zero():
    """新卡占比默认为零。"""
    assert AppSettings().new_review_ratio == 0


def test_ratio_zero_preserves_fixed_one_three_one():
    """占比为零时保持三加一加一结构。"""
    result = compose(
        due=["d0", "d1", "d2", "d3"],
        gaps=["g"],
        variants=["v"],
        new=["n0", "n1", "n2"],
        new_ratio=0,
    )

    assert result[0] == "g"
    assert sum(1 for item in result if item.startswith("d")) == 3
    assert sum(1 for item in result if item.startswith("n")) == 0
    assert "v" in result


def test_ratio_fifty_splits_remaining_slots():
    """占比五十时在剩余槽位平分。"""
    result = compose(
        due=["d0", "d1", "d2"],
        gaps=["g"],
        variants=["v"],
        new=["n0", "n1", "n2"],
        new_ratio=50,
    )

    assert result[0] == "g"
    assert sum(1 for item in result if item.startswith("d")) == 1
    assert sum(1 for item in result if item.startswith("n")) == 2
    assert "v" in result


def test_ratio_hundred_uses_new_cards():
    """占比一百时全部使用新卡。"""
    result = compose(
        due=["d0", "d1", "d2"],
        gaps=["g"],
        variants=["v"],
        new=["n0", "n1", "n2"],
        new_ratio=100,
    )

    assert result[0] == "g"
    assert sum(1 for item in result if item.startswith("d")) == 0
    assert sum(1 for item in result if item.startswith("n")) == 3
    assert "v" in result


def test_missing_new_cards_fall_back_to_due():
    """新卡不足时回退到期项。"""
    result = compose(
        due=["d0", "d1", "d2"],
        gaps=["g"],
        variants=["v"],
        new=["n0"],
        new_ratio=100,
    )

    assert sum(1 for item in result if item.startswith("n")) == 1
    assert sum(1 for item in result if item.startswith("d")) == 2


def test_review_pack_uses_only_unseen_cards_as_new():
    """只有未学过的卡片算新卡。"""
    cards = [_card(f"c{index}") for index in range(1, 7)]
    repository = InMemoryRepository()
    repository.save_receipt(_receipt("c1"), "c1-e1")

    questions = build_review_pack(
        repository, cards, NOW, total=5, new_ratio=100
    )

    assert len(questions) == 5
    assert all(question.card.id != "c1" for question in questions)


def test_review_package_can_generate_new_card_only_pack():
    """复习包可生成纯新卡包并注明占比。"""
    cards = [_card(f"c{index}") for index in range(1, 7)]
    repository = InMemoryRepository()
    repository.save_receipt(_receipt("c1"), "c1-e1")

    package = build_review_package(
        repository, cards, NOW, new_ratio=100
    )

    assert len(package.questions) == 5
    assert "新卡占比 100%" in package.reason
    assert all(question.card.id != "c1" for question in package.questions)
