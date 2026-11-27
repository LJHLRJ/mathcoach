"""连错诊断：确定性规则，不调用 LLM。

设计文档 §3.1 要求“连错 2 次先做错因诊断（五类之一）并一句话确认”。
这里只根据可观测信号分类，分类结果可由学生在 DIAGNOSE 阶段改选。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction

from .judge import normalize_answer, parse_pairs, parse_tokens
from .models import ErrorType, Exercise, ExerciseKind

_INEQUALITY = re.compile(r"([<>≤≥])\s*([-+]?\d+(?:\.\d+)?)")
_FLIP = {"<": ">", ">": "<", "≤": "≥", "≥": "≤"}
_LATIN = re.compile(r"[A-Za-z]+")
_STEP = re.compile(r"[-+]?\d+")


@dataclass(frozen=True)
class Diagnosis:
    """一次错因诊断：五类之一，加一句可展示的理由。"""

    error_type: ErrorType
    reason: str


def _number(text: str) -> float | None:
    """把作答转成有限浮点数；不可解析时返回 None。"""
    value = normalize_answer(text).replace(" ", "")
    if not value:
        return None
    try:
        number = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        try:
            number = float(value)
        except ValueError:
            return None
    return number if math.isfinite(number) else None


def _numeric_miss(correct: str, user: str) -> bool:
    """数值是否接近但不等：支持符号相反，容差为 0.01 或正确值的一半。"""
    correct_number, user_number = _number(correct), _number(user)
    if correct_number is None or user_number is None:
        return False
    if correct_number == user_number:
        return False
    if correct_number != 0 and math.isclose(
        user_number, -correct_number, rel_tol=0.0, abs_tol=1e-9
    ):
        return True
    return abs(user_number - correct_number) <= max(
        0.01, 0.5 * abs(correct_number)
    )


def _inequality_flip(correct: str, user: str) -> bool:
    """不等式方向是否写反，且边界值相同。"""
    correct_match = _INEQUALITY.findall(normalize_answer(correct))
    user_match = _INEQUALITY.findall(normalize_answer(user))
    if len(correct_match) != 1 or len(user_match) != 1:
        return False
    return (
        _FLIP.get(correct_match[0][0]) == user_match[0][0]
        and correct_match[0][1] == user_match[0][1]
    )


def _step_number(text: str) -> int | None:
    """把纯数字作答转成步骤号；非纯数字返回 None。"""
    match = _STEP.fullmatch(normalize_answer(text))
    return int(match.group()) if match else None


def _adjacent_step(correct: str, user: str) -> bool:
    """两个步骤号是否相邻。"""
    correct_step, user_step = _step_number(correct), _step_number(user)
    return (
        correct_step is not None
        and user_step is not None
        and abs(correct_step - user_step) == 1
    )


def _formula_miss(correct: str, user: str) -> bool:
    """答案与作答是否至少共享一个拉丁变量名。"""
    correct_names = set(_LATIN.findall(normalize_answer(correct)))
    user_names = set(_LATIN.findall(normalize_answer(user)))
    return bool(correct_names & user_names)


def diagnose(
    exercise: Exercise,
    wrong_answers: list[str],
    hint_requests: tuple[str, ...] = (),
) -> Diagnosis:
    """按固定优先级给出五类错因之一。

    优先级：主动要过步骤/答案 → 步骤排序 → 不等号反向/多选漏选/配对错配/
    相邻步骤 → 数值接近 → 公式结构 → 概念。分类只使用最近一次错误作答。

    Args:
        exercise: 当前题目。
        wrong_answers: 本题的错误作答历史，最后一项参与分类。
        hint_requests: 本题主动请求过的提示类型。

    Returns:
        ``Diagnosis``；``error_type`` 可由学生在 DIAGNOSE 阶段改选。
    """
    if any(request in ("step", "answer") for request in hint_requests):
        return Diagnosis(
            ErrorType.STEP_JUMP,
            "你先要了步骤/答案，说明解题路径还没自己走通",
        )

    correct = normalize_answer(exercise.answer)
    latest = normalize_answer(wrong_answers[-1]) if wrong_answers else ""

    if exercise.kind is ExerciseKind.PROOF_ORDER:
        return Diagnosis(ErrorType.STEP_JUMP, "步骤顺序没排对，属于路径/跳步问题")

    if exercise.kind in (ExerciseKind.CHOICE, ExerciseKind.FILL) and _inequality_flip(
        correct, latest
    ):
        return Diagnosis(ErrorType.READING, "不等号方向看反了")

    if exercise.kind is ExerciseKind.MULTI:
        user_set, correct_set = set(parse_tokens(latest)), set(parse_tokens(correct))
        if user_set and user_set < correct_set:
            return Diagnosis(ErrorType.READING, "漏选了正确选项，可能是读题不全")

    if exercise.kind is ExerciseKind.MATCH:
        user_pairs = parse_pairs(latest)
        correct_pairs = parse_pairs(correct)
        if user_pairs and correct_pairs:
            matched = sum(
                1
                for left, right in user_pairs.items()
                if correct_pairs.get(left) == right
            )
            if 0 < matched < len(correct_pairs):
                return Diagnosis(ErrorType.READING, "配对时看错了一部分对应关系")

    if exercise.kind is ExerciseKind.FIND_ERROR and _adjacent_step(correct, latest):
        return Diagnosis(ErrorType.READING, "看错了与正确步骤相邻的一步")

    if _numeric_miss(correct, latest):
        return Diagnosis(ErrorType.CALCULATION, "数值结果很接近但算错了")

    if exercise.kind in (
        ExerciseKind.EXPR,
        ExerciseKind.FILL,
        ExerciseKind.CHOICE,
    ) and _formula_miss(correct, latest):
        return Diagnosis(ErrorType.FORMULA, "公式结构与标准答案不一致")

    return Diagnosis(ErrorType.CONCEPT, "更可能是概念或前提没理清")
