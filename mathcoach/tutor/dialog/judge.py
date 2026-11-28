"""轻量三档判定：命中 / 部分命中 / 未命中。

只比较元数据中的可接受回答要点，不调用 domain 判定，也不判分。
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

from .models import DialogOutcome, FollowUpSpec

HIT_COVERAGE = 0.8
PARTIAL_COVERAGE = 0.3
PARTIAL_RELATIVE = 0.01
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")
_EXPONENT = re.compile(r"\^\d+(?:\.\d+)?")
_TOKEN = re.compile(
    r"[a-z]+|\d+(?:\.\d+)?(?:/\d+)?|[\u4e00-\u9fff]"
)


def _normalize(text: str) -> str:
    """统一全角、大小写、负号与常见数学符号。"""
    prepared = (
        text.replace("²", "^2")
        .replace("³", "^3")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("−", "-")
    )
    return unicodedata.normalize("NFKC", prepared).lower()


def _numbers(text: str) -> list[Fraction]:
    """提取可解析的数字/分数；表达式指数不算作答数字。"""
    values: list[Fraction] = []
    normalized = _EXPONENT.sub("", _normalize(text))
    for token in _NUMBER.findall(normalized):
        try:
            values.append(Fraction(token))
        except (ValueError, ZeroDivisionError):
            continue
    return values


def _tokens(text: str) -> set[str]:
    """中文按字、英文按词、数字按 token 切分。"""
    return set(_TOKEN.findall(_normalize(text)))


def _coverage(answer: str, point: str) -> float:
    """答案覆盖回答要点的比例。"""
    point_tokens = _tokens(point)
    if not point_tokens:
        return 0.0
    return len(_tokens(answer) & point_tokens) / len(point_tokens)


def _numeric_outcome(
    answer: str, points: tuple[str, ...]
) -> DialogOutcome | None:
    """数字比较；答案没有数字或要点没有数字时返回 None。"""
    answer_numbers = _numbers(answer)
    if not answer_numbers:
        return None
    point_numbers = [
        number for point in points for number in _numbers(point)
    ]
    if not point_numbers:
        return None
    for value in answer_numbers:
        if any(value == target for target in point_numbers):
            return DialogOutcome.HIT
    for value in answer_numbers:
        for target in point_numbers:
            if value == -target:
                return DialogOutcome.PARTIAL
            if (
                target != 0
                and abs(value - target) / abs(target) <= PARTIAL_RELATIVE
            ):
                return DialogOutcome.PARTIAL
            if target.denominator != 1 and value in (
                Fraction(target.numerator),
                Fraction(target.denominator),
            ):
                return DialogOutcome.PARTIAL
    return DialogOutcome.MISS


def judge_follow_up(spec: FollowUpSpec, answer: str) -> DialogOutcome:
    """按可接受回答要点给出三档判定。

    优先级：规范化完全匹配 > 数值等价 > 字符/词 token 覆盖率。
    含数字的要点要求答案也包含对应数字，避免只答出表达式却漏掉结果时
    被误判为命中。
    """
    if not answer.strip():
        return DialogOutcome.MISS
    normalized_answer = _normalize(answer).strip()
    if any(
        normalized_answer == _normalize(point).strip()
        for point in spec.acceptable
    ):
        return DialogOutcome.HIT
    numeric = _numeric_outcome(answer, spec.acceptable)
    if numeric is not None:
        return numeric
    best = 0.0
    for point in spec.acceptable:
        coverage = _coverage(answer, point)
        best = max(best, coverage)
        if coverage < HIT_COVERAGE:
            continue
        point_numbers = _numbers(point)
        answer_numbers = _numbers(answer)
        if point_numbers and not all(
            any(target == value for value in answer_numbers)
            for target in point_numbers
        ):
            continue
        return DialogOutcome.HIT
    if best >= PARTIAL_COVERAGE:
        return DialogOutcome.PARTIAL
    return DialogOutcome.MISS
