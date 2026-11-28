"""单步判定：表达式走 verify，数值/符号/顺序/配对走确定性比较。"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from fractions import Fraction

from ..verify.symbolic import (
    SymbolicVerdict,
    are_equivalent,
    validate_expression,
)
from .models import StepSpec, StepVerdict

StepVerifyFn = Callable[[str, str, frozenset[str]], SymbolicVerdict]

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")
_ORDER_SPLIT = re.compile(r"[,，、\s]+")
_RELATIVE_TOLERANCE = 1e-6
_ABSOLUTE_TOLERANCE = 1e-9


def _normalize(text: str) -> str:
    """统一全角、大小写、负号、乘除与空白。"""
    prepared = (
        text.replace("−", "-").replace("×", "*").replace("÷", "/")
    )
    return (
        unicodedata.normalize("NFKC", prepared)
        .lower()
        .replace(" ", "")
    )


def default_verify(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """默认使用 verify 的离线等价检查。"""
    return are_equivalent(left, right, variables, timeout_s=None)


def _as_fraction(text: str) -> Fraction | None:
    """把单个数字/分数转成有理数；不是纯数字时返回 None。"""
    normalized = _normalize(text)
    if _NUMBER.fullmatch(normalized) is None:
        return None
    try:
        return Fraction(normalized)
    except (ValueError, ZeroDivisionError):
        return None


def _close(left: Fraction, right: Fraction) -> bool:
    """数值比较：相对 1e-6、绝对 1e-9。"""
    if left == right:
        return True
    difference = abs(left - right)
    if difference <= _ABSOLUTE_TOLERANCE:
        return True
    if right == 0:
        return False
    return difference / abs(right) <= _RELATIVE_TOLERANCE


def _check_number(spec: StepSpec, answer: str) -> StepVerdict:
    """纯数值步骤：只接受数字或分数。"""
    value = _as_fraction(answer)
    expected = _as_fraction(spec.expected)
    if value is None or expected is None:
        return StepVerdict.REJECTED
    return (
        StepVerdict.CORRECT
        if _close(value, expected)
        else StepVerdict.INCORRECT
    )


def _check_text(spec: StepSpec, answer: str) -> StepVerdict:
    """符号或文字步骤：按可接受写法做规范化精确匹配。"""
    normalized = _normalize(answer)
    if not normalized:
        return StepVerdict.INCORRECT
    accepted = spec.acceptable or (spec.expected,)
    allowed = {_normalize(item) for item in accepted}
    return (
        StepVerdict.CORRECT
        if normalized in allowed
        else StepVerdict.INCORRECT
    )


def _check_order(spec: StepSpec, answer: str) -> StepVerdict:
    """顺序步骤：解析成整数序列后完全相等。"""
    values = [item for item in _ORDER_SPLIT.split(_normalize(answer)) if item]
    expected = [
        item
        for item in _ORDER_SPLIT.split(_normalize(spec.expected))
        if item
    ]
    try:
        actual_numbers = tuple(int(item) for item in values)
        expected_numbers = tuple(int(item) for item in expected)
    except ValueError:
        return StepVerdict.REJECTED
    if not actual_numbers:
        return StepVerdict.INCORRECT
    return (
        StepVerdict.CORRECT
        if actual_numbers == expected_numbers
        else StepVerdict.INCORRECT
    )


def _check_pair(spec: StepSpec, answer: str) -> StepVerdict:
    """配对步骤：统一分隔符与等号后做精确比较。"""
    normalized = _normalize(answer).replace("；", ";")
    expected = _normalize(spec.expected).replace("；", ";")
    if not normalized:
        return StepVerdict.INCORRECT
    return (
        StepVerdict.CORRECT
        if normalized == expected
        else StepVerdict.INCORRECT
    )


def _check_expression(
    spec: StepSpec, answer: str, verify_fn: StepVerifyFn
) -> StepVerdict:
    """表达式步骤：先过白名单，再做等价比较。"""
    variables = frozenset(spec.variables)
    rejected = validate_expression(answer, variables)
    if rejected is not None:
        return StepVerdict.REJECTED
    verdict = verify_fn(answer, spec.expected, variables)
    if verdict is SymbolicVerdict.EQUIVALENT:
        return StepVerdict.CORRECT
    if verdict is SymbolicVerdict.NOT_EQUIVALENT:
        return StepVerdict.INCORRECT
    if verdict is SymbolicVerdict.REJECTED:
        return StepVerdict.REJECTED
    return StepVerdict.UNVERIFIABLE


def check_step(
    spec: StepSpec,
    answer: str,
    *,
    verify_fn: StepVerifyFn | None = None,
) -> StepVerdict:
    """按步骤类型判定一次输入。

    Args:
        spec: 步骤元数据。
        answer: 学生输入。
        verify_fn: 表达式验证函数；缺省使用 verify 的等价检查。

    Returns:
        ``StepVerdict``；空输入直接判 INCORRECT。
    """
    if not answer.strip():
        return StepVerdict.INCORRECT
    if spec.input_kind == "expr":
        return _check_expression(spec, answer, verify_fn or default_verify)
    if spec.input_kind == "number":
        return _check_number(spec, answer)
    if spec.input_kind == "sign":
        return _check_text(spec, answer)
    if spec.input_kind == "order":
        return _check_order(spec, answer)
    if spec.input_kind == "pair":
        return _check_pair(spec, answer)
    return StepVerdict.OUT_OF_SCOPE
