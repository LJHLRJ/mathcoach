"""规则归因：把单次作答信号收敛为有限错因与可复核证据。

只读模块：
- 复用 ``domain.diagnosis.diagnose`` 的确定性规则；
- 复用 ``verify.symbolic`` 处理数学等价性断言；
- 不写 BKT、FSRS、错题或复习队列。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..domain.diagnosis import Diagnosis, diagnose
from ..domain.models import ErrorType, Exercise, ExerciseKind
from ..verify.symbolic import SymbolicVerdict, are_equivalent
from .errors import (
    ErrorCode,
    coerce_error_code,
    default_error_code,
    error_code_spec,
)

ActionKind = Literal[
    "review_prerequisite",
    "review_card",
    "practice_similar",
    "slow_down",
    "self_check",
]


@dataclass(frozen=True)
class MathClaim:
    """一条待验证的数学等价性断言。

    Attributes:
        left: 左侧表达式。
        right: 右侧表达式。
        variables: 允许的变量集合。
        timeout_s: 验证超时；None 表示使用验证层默认上限。
    """

    left: str
    right: str
    variables: frozenset[str]
    timeout_s: float | None = None


@dataclass(frozen=True)
class VerifiedClaim:
    """数学断言经过验证层后的结果。

    Attributes:
        verdict: 验证结论。
        text: 可直接展示的说明。
        needs_manual_check: 是否必须提示自行核对。
    """

    verdict: SymbolicVerdict
    text: str
    needs_manual_check: bool


@dataclass(frozen=True)
class Evidence:
    """一条归因证据；只含统计值与确定性说明，不含原始作答。"""

    metric_id: str
    value: str | int | float | None
    text: str


@dataclass(frozen=True)
class SuggestedAction:
    """确定性的下一步建议。"""

    kind: ActionKind
    text: str
    target_card_id: str | None = None


@dataclass(frozen=True)
class Attribution:
    """规则归因结果，供模板叙事或 LLM 叙事消费。"""

    error_type: ErrorType
    error_code: ErrorCode
    confidence: float
    underlying_cause: str
    suggested_next_action: SuggestedAction
    evidence: tuple[Evidence, ...]
    caveats: tuple[str, ...]
    needs_verification: bool
    verified_claim: VerifiedClaim | None = None

    def to_dict(self) -> dict[str, object]:
        """转为可直接序列化的映射；不包含原始作答文本。"""
        claim = None
        if self.verified_claim is not None:
            claim = {
                "verdict": self.verified_claim.verdict.value,
                "text": self.verified_claim.text,
                "needs_manual_check": self.verified_claim.needs_manual_check,
            }
        return {
            "error_type": self.error_type.value,
            "error_code": self.error_code.value,
            "confidence": self.confidence,
            "underlying_cause": self.underlying_cause,
            "suggested_next_action": {
                "kind": self.suggested_next_action.kind,
                "text": self.suggested_next_action.text,
                "target_card_id": self.suggested_next_action.target_card_id,
            },
            "evidence": [
                {
                    "metric_id": item.metric_id,
                    "value": item.value,
                    "text": item.text,
                }
                for item in self.evidence
            ],
            "caveats": list(self.caveats),
            "needs_verification": self.needs_verification,
            "verified_claim": claim,
        }


def resolve_error_code(
    error_type: ErrorType,
    exercise_kind: ExerciseKind,
    hint_requests: tuple[str, ...],
) -> ErrorCode:
    """根据题型与提示请求选择确定性子类。

    Args:
        error_type: 顶层错因。
        exercise_kind: 题型。
        hint_requests: 主动请求过的提示类型。

    Returns:
        与顶层错因一致的 ``ErrorCode``。
    """
    if error_type is ErrorType.STEP_JUMP:
        if any(kind in ("step", "answer") for kind in hint_requests):
            return ErrorCode.STEP_JUMP_HINT_DEPENDENCY
        if exercise_kind is ExerciseKind.PROOF_ORDER:
            return ErrorCode.STEP_JUMP_ORDER_ERROR
    if error_type is ErrorType.READING:
        if exercise_kind is ExerciseKind.MULTI:
            return ErrorCode.READING_OPTION_OMISSION
        if exercise_kind is ExerciseKind.MATCH:
            return ErrorCode.READING_PAIRING_MISMATCH
        if exercise_kind is ExerciseKind.FIND_ERROR:
            return ErrorCode.READING_ADJACENT_STEP
    return default_error_code(error_type)


def verify_math_claim(claim: MathClaim) -> VerifiedClaim:
    """用验证层检查数学断言，不自行判断等价性。

    Args:
        claim: 待验证断言。

    Returns:
        ``VerifiedClaim``；无法确认时标记为需人工核对。
    """
    if claim.timeout_s is None:
        verdict = are_equivalent(claim.left, claim.right, claim.variables)
    else:
        verdict = are_equivalent(
            claim.left,
            claim.right,
            claim.variables,
            timeout_s=claim.timeout_s,
        )
    if verdict is SymbolicVerdict.EQUIVALENT:
        return VerifiedClaim(verdict, "两侧表达式等价。", False)
    if verdict is SymbolicVerdict.NOT_EQUIVALENT:
        return VerifiedClaim(verdict, "两侧表达式不等价。", False)
    if verdict is SymbolicVerdict.REJECTED:
        return VerifiedClaim(
            verdict,
            "表达式未通过安全校验，建议自行核对，不据此下结论。",
            True,
        )
    return VerifiedClaim(
        verdict,
        "无法自动验证等价性，建议自行核对，不据此下结论。",
        True,
    )


def _action_for(
    code: ErrorCode,
    card_id: str,
    prerequisite_card_id: str | None,
) -> SuggestedAction:
    """按子类给出确定性下一步。"""
    error_type = error_code_spec(code).error_type
    if code is ErrorCode.CONCEPT_PREREQUISITE_GAP:
        return SuggestedAction(
            "review_prerequisite",
            "先回顾先修概念，再回来重做本题。",
            prerequisite_card_id or card_id,
        )
    if error_type is ErrorType.CONCEPT:
        return SuggestedAction(
            "review_card", "重看本卡定义与反例，再做一道同类题。", card_id
        )
    if error_type is ErrorType.FORMULA:
        return SuggestedAction(
            "review_card", "回顾公式卡片，并写出公式的适用条件。", card_id
        )
    if error_type is ErrorType.CALCULATION:
        return SuggestedAction(
            "slow_down", "放慢计算，把中间结果逐行写出来。", card_id
        )
    if error_type is ErrorType.READING:
        return SuggestedAction(
            "self_check", "先圈出条件与选项，再开始作答。", card_id
        )
    return SuggestedAction(
        "self_check", "先自己写出下一步，再决定是否请求提示。", card_id
    )


def _cause_for(
    code: ErrorCode,
    max_hint_level: int,
    attempt_count: int,
) -> str:
    """按子类生成确定性归因说明。"""
    if code is ErrorCode.CONCEPT_PREREQUISITE_GAP:
        return "先修概念近期错误比例偏高，更接近先修概念缺口。"
    if code is ErrorCode.STEP_JUMP_HINT_DEPENDENCY:
        return (
            f"本题最高用到 L{max_hint_level} 提示，关键步骤依赖提示，"
            "更接近跳步或提示依赖。"
        )
    if code is ErrorCode.STEP_JUMP_ORDER_ERROR:
        return "步骤顺序没有排对，更接近路径或跳步问题。"
    if code is ErrorCode.READING_OPTION_OMISSION:
        return "多选只选了一部分，更接近读题不全。"
    if code is ErrorCode.READING_PAIRING_MISMATCH:
        return "配对关系只对了一部分，更接近读题偏差。"
    if code is ErrorCode.READING_ADJACENT_STEP:
        return "看错了与正确步骤相邻的一步，更接近读题偏差。"
    if code is ErrorCode.CALCULATION_NUMERIC_NEAR_MISS:
        return "数值结果很接近但不等，更接近计算失误。"
    if code is ErrorCode.FORMULA_STRUCTURE_ERROR:
        return "答案与标准公式的结构不一致，更接近公式记错。"
    return (
        f"本题共作答 {attempt_count} 次，最高提示 L{max_hint_level}，"
        f"更接近「{error_code_spec(code).label}」。"
    )


def build_attribution(
    exercise: Exercise,
    wrong_answers: list[str],
    hint_requests: tuple[str, ...] = (),
    *,
    max_hint_level: int = 1,
    attempt_count: int = 1,
    duration_s: int | None = None,
    diagnosis: Diagnosis | None = None,
    error_code: ErrorCode | str | None = None,
    prerequisite_card_id: str | None = None,
    math_claim: MathClaim | None = None,
) -> Attribution:
    """把单次作答信号收敛为规则归因。

    Args:
        exercise: 当前题目。
        wrong_answers: 本题错误作答文本，仅用于复用确定性诊断。
        hint_requests: 主动请求过的提示类型。
        max_hint_level: 本题最高提示层级。
        attempt_count: 本题已作答次数。
        duration_s: 本题用时；未知时为 None。
        diagnosis: 已有诊断结果；为空时按 ``wrong_answers`` 现场诊断。
        error_code: 上层已确定的子类；为空时按题型与提示请求选择。
        prerequisite_card_id: 先修卡 ID，用于给出复习目标。
        math_claim: 可选数学断言；只经验证层后进入证据。

    Returns:
        ``Attribution``。

    Raises:
        ValueError: 既没有诊断结果也没有错误作答。
    """
    if diagnosis is None:
        if not wrong_answers:
            raise ValueError("wrong_answers 与 diagnosis 至少提供一个")
        diagnosis = diagnose(exercise, wrong_answers, hint_requests)

    code = default_error_code(diagnosis.error_type)
    if error_code is not None:
        candidate = coerce_error_code(error_code, diagnosis.error_type)
        if error_code_spec(candidate).error_type is diagnosis.error_type:
            code = candidate
    else:
        code = resolve_error_code(
            diagnosis.error_type, exercise.kind, hint_requests
        )
    spec = error_code_spec(code)
    evidence = [
        Evidence("attempt.count", attempt_count, f"本题第 {attempt_count} 次作答"),
        Evidence("hint.max_level", max_hint_level, f"最高提示 L{max_hint_level}"),
        Evidence("diagnosis.rule", diagnosis.error_type.value, diagnosis.reason),
    ]
    if hint_requests:
        evidence.append(
            Evidence(
                "hint.requests",
                len(hint_requests),
                "主动请求提示：" + "/".join(hint_requests),
            )
        )
    if duration_s is not None:
        evidence.append(
            Evidence("time.attempt_s", duration_s, f"本题用时 {duration_s} 秒")
        )

    verified_claim = (
        verify_math_claim(math_claim) if math_claim is not None else None
    )
    if verified_claim is not None:
        evidence.append(
            Evidence(
                "math.claim",
                verified_claim.verdict.value,
                verified_claim.text,
            )
        )

    caveats = ["仅基于本题可观测信号与规则诊断，不代表完整能力判断。"]
    if verified_claim is not None and verified_claim.needs_manual_check:
        caveats.append("涉及数学等价性的内容未自动确认，建议自行核对。")

    return Attribution(
        error_type=diagnosis.error_type,
        error_code=code,
        confidence=spec.default_confidence,
        underlying_cause=_cause_for(code, max_hint_level, attempt_count),
        suggested_next_action=_action_for(
            code, exercise.card_id, prerequisite_card_id
        ),
        evidence=tuple(evidence),
        caveats=tuple(caveats),
        needs_verification=bool(
            verified_claim is not None and verified_claim.needs_manual_check
        ),
        verified_claim=verified_claim,
    )
