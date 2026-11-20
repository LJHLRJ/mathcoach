"""仓库内真实内容必须能通过严格模式校验。"""
from collections import Counter
from pathlib import Path

from mathcoach.content.loader import load_content
from mathcoach.domain.models import ExerciseKind

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def test_real_content_loads_in_strict_mode():
    cards, result = load_content(CONTENT_ROOT, strict=True)
    assert result.ok
    assert result.warnings == []
    assert 115 <= len(cards) <= 125


def test_each_course_has_five_to_eight_cards():
    cards, _ = load_content(CONTENT_ROOT, strict=True)
    counts = Counter((card.stage.value, card.course) for card in cards)
    assert len(counts) == 23
    assert all(5 <= count <= 8 for count in counts.values())


def test_every_card_has_three_exercises_and_a_variant():
    cards, _ = load_content(CONTENT_ROOT, strict=True)
    for card in cards:
        assert len(card.exercises) == 3, card.id
        assert any(exercise.variants for exercise in card.exercises), card.id


def test_all_eight_exercise_kinds_are_covered():
    cards, _ = load_content(CONTENT_ROOT, strict=True)
    kinds = {exercise.kind for card in cards for exercise in card.exercises}
    assert kinds == set(ExerciseKind)


def test_card_order_is_deterministic():
    first, _ = load_content(CONTENT_ROOT, strict=True)
    second, _ = load_content(CONTENT_ROOT, strict=True)
    assert [card.id for card in first] == [card.id for card in second]
