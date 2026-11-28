"""规则归因：子类选择、证据与数学断言降级。"""
import json

import pytest

from mathcoach.analytics import (
    ErrorCode,
    MathClaim,
    build_attribution,
    resolve_error_code,
    verify_math_claim,
)
from mathcoach.domain.diagnosis import Diagnosis
from mathcoach.domain.models import ErrorType, Exercise, ExerciseKind
from mathcoach.verify.symbolic import SymbolicVerdict


def _exercise(
    kind: ExerciseKind = ExerciseKind.CHOICE,
    answer: str = "A",
    options: tuple[str, ...] = ("A", "B"),
) -> Exercise:
    """构造规则归因用的练习。"""
    return Exercise(
        id="card-1-e1",
        card_id="card-1",
        kind=kind,
        stem="题干",
        answer=answer,
        solution_outline="标准思路",
        options=options,
    )


def test_hint_request_maps_to_step_jump_dependency():
    """主动请求步骤提示时归因为提示依赖。"""
    attribution = build_attribution(
        _exercise(),
        ["SECRET_WRONG"],
        ("step",),
        max_hint_level=4,
        attempt_count=2,
        duration_s=30,
    )

    assert attribution.error_type is ErrorType.STEP_JUMP
    assert attribution.error_code is ErrorCode.STEP_JUMP_HINT_DEPENDENCY
    assert attribution.confidence == 0.9
    assert attribution.suggested_next_action.kind == "self_check"
    assert any(
        item.metric_id == "hint.requests"
        for item in attribution.evidence
    )


def test_multi_subset_maps_to_option_omission():
    """多选漏选归因为读题偏差下的漏选。"""
    exercise = _exercise(
        ExerciseKind.MULTI, "A,C", ("A", "B", "C")
    )
    attribution = build_attribution(exercise, ["A"])

    assert attribution.error_type is ErrorType.READING
    assert attribution.error_code is ErrorCode.READING_OPTION_OMISSION
    assert attribution.confidence == 0.8


def test_proof_order_maps_to_order_error():
    """证明排序题归因为步骤顺序错误。"""
    code = resolve_error_code(
        ErrorType.STEP_JUMP, ExerciseKind.PROOF_ORDER, ()
    )
    assert code is ErrorCode.STEP_JUMP_ORDER_ERROR


def test_provided_diagnosis_is_reused():
    """已有诊断结果时不重复跑规则。"""
    diagnosis = Diagnosis(ErrorType.CALCULATION, "数值接近但不等")
    attribution = build_attribution(
        _exercise(), [], diagnosis=diagnosis
    )

    assert attribution.error_type is ErrorType.CALCULATION
    assert (
        attribution.error_code
        is ErrorCode.CALCULATION_NUMERIC_NEAR_MISS
    )
    assert attribution.suggested_next_action.kind == "slow_down"


def test_missing_diagnosis_and_answers_raise():
    """没有诊断也没有错误作答时拒绝构造。"""
    with pytest.raises(ValueError):
        build_attribution(_exercise(), [])


def test_math_claim_rejection_requires_manual_check():
    """验证层拒绝时标记为需要人工核对。"""
    claim = MathClaim(
        "__import__('os')", "x", frozenset({"x"})
    )
    verified = verify_math_claim(claim)

    assert verified.verdict is SymbolicVerdict.REJECTED
    assert verified.needs_manual_check is True
    assert "建议自行核对" in verified.text


def test_mismatched_provided_code_falls_back_to_default():
    """上层子类与顶层诊断不一致时回落到默认子类。"""
    diagnosis = Diagnosis(ErrorType.CONCEPT, "概念没理清")
    attribution = build_attribution(
        _exercise(),
        [],
        diagnosis=diagnosis,
        error_code=ErrorCode.READING_INEQUALITY_DIRECTION,
    )

    assert attribution.error_type is ErrorType.CONCEPT
    assert (
        attribution.error_code
        is ErrorCode.CONCEPT_DEFINITION_CONFUSION
    )


def test_attribution_does_not_expose_raw_answer():
    """归因摘要不包含原始错误作答。"""
    attribution = build_attribution(
        _exercise(), ["SECRET_WRONG"], ("step",)
    )
    payload = json.dumps(attribution.to_dict(), ensure_ascii=False)

    assert "SECRET_WRONG" not in payload
    assert "hint.max_level" in payload
