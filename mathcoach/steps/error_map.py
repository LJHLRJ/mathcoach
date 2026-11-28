"""步骤级错因映射：只读 step_tag 与判定结果，不改题级诊断。"""
from __future__ import annotations

from ..domain.models import ErrorType
from .models import StepSpec, StepVerdict

_STEP_ERRORS = {
    "formula": ErrorType.FORMULA,
    "identity": ErrorType.FORMULA,
    "calculation": ErrorType.CALCULATION,
    "sign": ErrorType.CALCULATION,
    "value": ErrorType.CALCULATION,
    "conversion": ErrorType.READING,
    "procedure": ErrorType.STEP_JUMP,
    "order": ErrorType.STEP_JUMP,
}


def step_error_type(
    spec: StepSpec, verdict: StepVerdict
) -> ErrorType | None:
    """把答错步骤映射到五类错因。

    只处理 ``INCORRECT``；无法核对、格式拒绝、范围外都不产生错因，
    由题级 ``diagnose`` 或人工核对兜底。未知 ``step_tag`` 返回 None。
    """
    if verdict is not StepVerdict.INCORRECT:
        return None
    return _STEP_ERRORS.get(spec.step_tag)
