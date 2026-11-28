"""步骤判定展示：行级徽标与原因，不泄露标准答案。"""
from mathcoach.steps import StepSpec, StepVerdict
from mathcoach.steps.models import StepAttempt
from mathcoach.steps.presentation import (
    StepMarker,
    build_step_reason,
    input_kind_hint,
    present_verdict,
    step_tag_label,
)


def _attempt(verdict: StepVerdict, input_text: str = "3") -> StepAttempt:
    return StepAttempt(
        run_id="run",
        exercise_id="hs-trig-004-e1",
        step_index=1,
        input=input_text,
        verdict=verdict,
        expected="42",
        kc_id="kc-hs-trig-004-f1",
        step_tag="formula",
    )


def _spec() -> StepSpec:
    return StepSpec(
        exercise_id="hs-trig-004-e1",
        index=1,
        prompt="ω 等于多少？",
        expected="42",
        kc_id="kc-hs-trig-004-f1",
        step_tag="formula",
        input_kind="expr",
    )


def test_each_verdict_has_tone_and_label():
    """五种判定都有行级色调与文案。"""
    expected = {
        StepVerdict.CORRECT: ("success", "正确"),
        StepVerdict.INCORRECT: ("error", "这一步不对"),
        StepVerdict.UNVERIFIABLE: ("info", "无法自动核对"),
        StepVerdict.REJECTED: ("info", "输入不符合格式"),
        StepVerdict.OUT_OF_SCOPE: ("info", "超出步骤范围"),
    }
    for verdict, (tone, label) in expected.items():
        marker = present_verdict(verdict)
        assert isinstance(marker, StepMarker)
        assert marker.tone == tone
        assert marker.label == label


def test_step_tag_and_input_hint():
    """步骤标签与输入格式有中文说明。"""
    assert step_tag_label("formula") == "公式"
    assert step_tag_label("calculation") == "计算"
    assert step_tag_label("unknown-tag") == "unknown-tag"
    assert "表达式" in input_kind_hint("expr")
    assert "数字" in input_kind_hint("number")
    assert input_kind_hint("unknown") == "按题目要求填写"


def test_reason_explains_without_expected_answer():
    """原因说明包含考查点与建议，但不展示标准答案。"""
    reason = build_step_reason(_spec(), _attempt(StepVerdict.INCORRECT))

    assert "公式" in reason
    assert "数学表达式" in reason
    assert "公式记错" in reason
    assert "建议" in reason
    assert "42" not in reason


def test_correct_reason_has_no_revision_suggestion():
    """正确时不出现回看建议。"""
    reason = build_step_reason(_spec(), _attempt(StepVerdict.CORRECT))

    assert "一致" in reason
    assert "建议" not in reason
