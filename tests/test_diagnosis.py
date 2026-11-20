"""连错诊断：固定优先级、确定性、可被用户改选。"""
from mathcoach.domain.diagnosis import diagnose
from mathcoach.domain.models import ErrorType, Exercise, ExerciseKind


def _exercise(kind: ExerciseKind, answer: str, **fields) -> Exercise:
    return Exercise(
        id="hs-001-e1",
        card_id="hs-001",
        kind=kind,
        stem="题干",
        answer=answer,
        solution_outline="标准思路",
        **fields,
    )


def test_requesting_steps_is_step_jump():
    result = diagnose(_exercise(ExerciseKind.CHOICE, "A"), ["B"], ("step",))
    assert result.error_type is ErrorType.STEP_JUMP


def test_proof_order_wrong_is_step_jump():
    result = diagnose(_exercise(ExerciseKind.PROOF_ORDER, "1,2,3"), ["3,2,1"])
    assert result.error_type is ErrorType.STEP_JUMP


def test_inequality_direction_flip_is_reading():
    exercise = _exercise(ExerciseKind.CHOICE, "x ≥ 2", options=("x ≥ 2", "x ≤ 2"))
    result = diagnose(exercise, ["x ≤ 2"])
    assert result.error_type is ErrorType.READING


def test_multi_subset_is_reading():
    exercise = _exercise(ExerciseKind.MULTI, "A,C", options=("A", "B", "C"))
    result = diagnose(exercise, ["A"])
    assert result.error_type is ErrorType.READING


def test_match_partial_is_reading():
    exercise = _exercise(ExerciseKind.MATCH, "A=1;B=2")
    result = diagnose(exercise, ["A=1;B=3"])
    assert result.error_type is ErrorType.READING


def test_find_error_adjacent_step_is_reading():
    exercise = _exercise(ExerciseKind.FIND_ERROR, "3", options=("1", "2", "3"))
    result = diagnose(exercise, ["2"])
    assert result.error_type is ErrorType.READING


def test_numeric_near_miss_is_calculation():
    assert diagnose(_exercise(ExerciseKind.FILL, "42"), ["24"]).error_type is ErrorType.CALCULATION
    assert diagnose(_exercise(ExerciseKind.FILL, "1/2"), ["0.6"]).error_type is ErrorType.CALCULATION


def test_formula_structure_mismatch():
    result = diagnose(_exercise(ExerciseKind.EXPR, "2*x + 1"), ["2*x - 1"])
    assert result.error_type is ErrorType.FORMULA


def test_unclassified_defaults_to_concept():
    exercise = _exercise(ExerciseKind.CHOICE, "高阶", options=("高阶", "同阶"))
    result = diagnose(exercise, ["同阶"])
    assert result.error_type is ErrorType.CONCEPT


def test_truefalse_wrong_defaults_to_concept():
    result = diagnose(_exercise(ExerciseKind.TRUEFALSE, "True"), ["False"])
    assert result.error_type is ErrorType.CONCEPT
