"""步骤级错因映射：只对答错步骤给出五类错因。"""
from mathcoach.domain.models import ErrorType
from mathcoach.steps import StepSpec, StepVerdict
from mathcoach.steps.error_map import step_error_type


def _spec(tag: str) -> StepSpec:
    return StepSpec(
        exercise_id="hs-trig-004-e1",
        index=1,
        prompt="步骤",
        expected="1",
        step_tag=tag,
    )


def test_tag_mapping():
    """公式/恒等式、计算、换算、步骤分别映射到对应错因。"""
    assert step_error_type(_spec("formula"), StepVerdict.INCORRECT) is (
        ErrorType.FORMULA
    )
    assert step_error_type(_spec("identity"), StepVerdict.INCORRECT) is (
        ErrorType.FORMULA
    )
    assert step_error_type(_spec("calculation"), StepVerdict.INCORRECT) is (
        ErrorType.CALCULATION
    )
    assert step_error_type(_spec("sign"), StepVerdict.INCORRECT) is (
        ErrorType.CALCULATION
    )
    assert step_error_type(_spec("value"), StepVerdict.INCORRECT) is (
        ErrorType.CALCULATION
    )
    assert step_error_type(_spec("conversion"), StepVerdict.INCORRECT) is (
        ErrorType.READING
    )
    assert step_error_type(_spec("procedure"), StepVerdict.INCORRECT) is (
        ErrorType.STEP_JUMP
    )
    assert step_error_type(_spec("order"), StepVerdict.INCORRECT) is (
        ErrorType.STEP_JUMP
    )


def test_only_incorrect_verdict_maps():
    """正确、无法核对、格式拒绝与范围外不产生步骤错因。"""
    for verdict in (
        StepVerdict.CORRECT,
        StepVerdict.UNVERIFIABLE,
        StepVerdict.REJECTED,
        StepVerdict.OUT_OF_SCOPE,
    ):
        assert step_error_type(_spec("formula"), verdict) is None


def test_unknown_tag_returns_none():
    """未知 step_tag 回退题级诊断。"""
    assert step_error_type(_spec("unknown"), StepVerdict.INCORRECT) is None
