"""M1 只实现 choice 精确匹配；其他题型必须显式报未实现。"""
import pytest

from mathcoach.domain.judge import judge
from mathcoach.domain.models import Exercise, ExerciseKind


def _choice() -> Exercise:
    return Exercise(
        id="hs-001-e1",
        card_id="hs-001",
        kind=ExerciseKind.CHOICE,
        stem="2 + 2 = ?",
        answer="4",
        solution_outline="直接相加",
        options=("3", "4"),
    )


def test_choice_correct():
    assert judge(_choice(), "4") is True


def test_choice_wrong():
    assert judge(_choice(), "3") is False


def test_other_kind_not_implemented_yet():
    exercise = Exercise(
        id="hs-001-e2",
        card_id="hs-001",
        kind=ExerciseKind.FILL,
        stem="2 + 2 = ?",
        answer="4",
        solution_outline="直接相加",
    )
    with pytest.raises(NotImplementedError):
        judge(exercise, "4")
