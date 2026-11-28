"""错因子类：五类顶层错因下的有限、可聚合编码。

顶层仍使用 ``domain.models.ErrorType``；子类只用于分析归因，不改变现有
错题表与诊断结果。每个编码绑定一个顶层错因、展示名称、默认置信度与
对应的确定性规则来源。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..domain.models import ErrorType


class ErrorCode(str, Enum):
    """有限错因子类；取值稳定，可直接进入统计与 JSON。"""

    CONCEPT_PREREQUISITE_GAP = "concept.prerequisite_gap"
    CONCEPT_DEFINITION_CONFUSION = "concept.definition_confusion"
    CONCEPT_BOUNDARY_CONDITION = "concept.boundary_condition"

    FORMULA_RECALL_ERROR = "formula.recall_error"
    FORMULA_STRUCTURE_ERROR = "formula.structure_error"
    FORMULA_SIGN_ERROR = "formula.sign_error"

    CALCULATION_ARITHMETIC_SLIP = "calculation.arithmetic_slip"
    CALCULATION_ALGEBRA_SLIP = "calculation.algebra_slip"
    CALCULATION_NUMERIC_NEAR_MISS = "calculation.numeric_near_miss"
    CALCULATION_UNIT_ERROR = "calculation.unit_error"

    READING_INEQUALITY_DIRECTION = "reading.inequality_direction"
    READING_OPTION_OMISSION = "reading.option_omission"
    READING_PAIRING_MISMATCH = "reading.pairing_mismatch"
    READING_ADJACENT_STEP = "reading.adjacent_step"
    READING_CONDITION_MISREAD = "reading.condition_misread"

    STEP_JUMP_HINT_DEPENDENCY = "step_jump.hint_dependency"
    STEP_JUMP_ORDER_ERROR = "step_jump.order_error"
    STEP_JUMP_MISSING_JUSTIFICATION = "step_jump.missing_justification"


@dataclass(frozen=True)
class ErrorCodeSpec:
    """一个错因子类的静态定义。

    Attributes:
        code: 子类编码。
        error_type: 对应顶层错因。
        label: 展示名称。
        default_confidence: 规则命中时的默认置信度，范围 0–1。
        source_rule: 对应的确定性规则来源，便于追溯。
    """

    code: ErrorCode
    error_type: ErrorType
    label: str
    default_confidence: float
    source_rule: str


ERROR_CODE_SPECS: tuple[ErrorCodeSpec, ...] = (
    ErrorCodeSpec(
        ErrorCode.CONCEPT_PREREQUISITE_GAP,
        ErrorType.CONCEPT,
        "先修概念缺口",
        0.7,
        "prerequisites.trace_gap",
    ),
    ErrorCodeSpec(
        ErrorCode.CONCEPT_DEFINITION_CONFUSION,
        ErrorType.CONCEPT,
        "定义或前提混淆",
        0.4,
        "diagnosis.default",
    ),
    ErrorCodeSpec(
        ErrorCode.CONCEPT_BOUNDARY_CONDITION,
        ErrorType.CONCEPT,
        "边界条件遗漏",
        0.45,
        "diagnosis.default",
    ),
    ErrorCodeSpec(
        ErrorCode.FORMULA_RECALL_ERROR,
        ErrorType.FORMULA,
        "公式记忆错误",
        0.55,
        "diagnosis.formula_miss",
    ),
    ErrorCodeSpec(
        ErrorCode.FORMULA_STRUCTURE_ERROR,
        ErrorType.FORMULA,
        "公式结构不符",
        0.55,
        "diagnosis.formula_miss",
    ),
    ErrorCodeSpec(
        ErrorCode.FORMULA_SIGN_ERROR,
        ErrorType.FORMULA,
        "符号写反",
        0.6,
        "diagnosis.formula_miss",
    ),
    ErrorCodeSpec(
        ErrorCode.CALCULATION_ARITHMETIC_SLIP,
        ErrorType.CALCULATION,
        "算术失误",
        0.65,
        "diagnosis.numeric_miss",
    ),
    ErrorCodeSpec(
        ErrorCode.CALCULATION_ALGEBRA_SLIP,
        ErrorType.CALCULATION,
        "代数变形失误",
        0.6,
        "diagnosis.numeric_miss",
    ),
    ErrorCodeSpec(
        ErrorCode.CALCULATION_NUMERIC_NEAR_MISS,
        ErrorType.CALCULATION,
        "数值接近但不等",
        0.65,
        "diagnosis.numeric_miss",
    ),
    ErrorCodeSpec(
        ErrorCode.CALCULATION_UNIT_ERROR,
        ErrorType.CALCULATION,
        "单位或量纲错误",
        0.5,
        "diagnosis.numeric_miss",
    ),
    ErrorCodeSpec(
        ErrorCode.READING_INEQUALITY_DIRECTION,
        ErrorType.READING,
        "不等号方向看反",
        0.8,
        "diagnosis.inequality_flip",
    ),
    ErrorCodeSpec(
        ErrorCode.READING_OPTION_OMISSION,
        ErrorType.READING,
        "多选漏选",
        0.8,
        "diagnosis.multi_subset",
    ),
    ErrorCodeSpec(
        ErrorCode.READING_PAIRING_MISMATCH,
        ErrorType.READING,
        "配对错配",
        0.8,
        "diagnosis.match_partial",
    ),
    ErrorCodeSpec(
        ErrorCode.READING_ADJACENT_STEP,
        ErrorType.READING,
        "相邻步骤看错",
        0.8,
        "diagnosis.adjacent_step",
    ),
    ErrorCodeSpec(
        ErrorCode.READING_CONDITION_MISREAD,
        ErrorType.READING,
        "条件误读",
        0.6,
        "diagnosis.default",
    ),
    ErrorCodeSpec(
        ErrorCode.STEP_JUMP_HINT_DEPENDENCY,
        ErrorType.STEP_JUMP,
        "依赖步骤或答案提示",
        0.9,
        "diagnosis.hint_requests",
    ),
    ErrorCodeSpec(
        ErrorCode.STEP_JUMP_ORDER_ERROR,
        ErrorType.STEP_JUMP,
        "步骤顺序错误",
        0.85,
        "diagnosis.proof_order",
    ),
    ErrorCodeSpec(
        ErrorCode.STEP_JUMP_MISSING_JUSTIFICATION,
        ErrorType.STEP_JUMP,
        "缺少论证步骤",
        0.6,
        "diagnosis.default",
    ),
)

_SPEC_BY_CODE = {spec.code: spec for spec in ERROR_CODE_SPECS}

DEFAULT_CODE_BY_ERROR_TYPE: dict[ErrorType, ErrorCode] = {
    ErrorType.CONCEPT: ErrorCode.CONCEPT_DEFINITION_CONFUSION,
    ErrorType.FORMULA: ErrorCode.FORMULA_STRUCTURE_ERROR,
    ErrorType.CALCULATION: ErrorCode.CALCULATION_NUMERIC_NEAR_MISS,
    ErrorType.READING: ErrorCode.READING_CONDITION_MISREAD,
    ErrorType.STEP_JUMP: ErrorCode.STEP_JUMP_HINT_DEPENDENCY,
}


def default_error_code(error_type: ErrorType) -> ErrorCode:
    """返回顶层错因的默认子类。

    Args:
        error_type: 顶层错因。

    Returns:
        对应的默认 ``ErrorCode``。
    """
    return DEFAULT_CODE_BY_ERROR_TYPE[error_type]


def error_code_spec(code: ErrorCode) -> ErrorCodeSpec:
    """返回子类的静态定义。

    Args:
        code: 错因子类。

    Returns:
        ``ErrorCodeSpec``。
    """
    return _SPEC_BY_CODE[code]


def error_type_for_code(code: ErrorCode) -> ErrorType:
    """返回子类编码对应的顶层错因。

    Args:
        code: 错因子类。

    Returns:
        顶层 ``ErrorType``。
    """
    return _SPEC_BY_CODE[code].error_type


def coerce_error_code(
    value: str | ErrorCode | None, fallback: ErrorType
) -> ErrorCode:
    """把外部输入收敛到已知子类。

    只接受 ``ErrorCode`` 或它的字符串值；顶层中文错因、空值与未知字符串
    都回落到 ``fallback`` 的默认子类，避免自由标签进入统计。

    Args:
        value: 待收敛的值。
        fallback: 无法识别时使用的顶层错因。

    Returns:
        已知的 ``ErrorCode``。
    """
    if isinstance(value, ErrorCode):
        return value
    if isinstance(value, str):
        try:
            return ErrorCode(value)
        except ValueError:
            pass
    return default_error_code(fallback)
