"""8 种题型判定器：确定性纯函数，不调用 LLM。

答案约定（YAML 加载期会规范化成这些形式）：
- ``multi``：逗号分隔，如 ``A,C``；
- ``proof_order``：逗号分隔的步骤序列，如 ``1,2,3``；
- ``match``：分号/逗号分隔的配对，如 ``A=1;B=2``；
- ``truefalse``：``True`` / ``False``（大小写、对错、是否均可）；
- ``fill``：归一化后精确匹配，数值题带 1e-6 容差；
- ``expr``：受限 AST → sympy 等价判定，拒绝/超时返回“需人工核对”。
"""
from __future__ import annotations

import ast
import math
import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction

from ..verify.symbolic import (
    SymbolicVerdict,
    are_equivalent,
    expr_variables,
    validate_expression,
)
from .models import Exercise, ExerciseKind

_TRANSLATE = str.maketrans(
    {
        "−": "-",
        "–": "-",
        "—": "-",
        "×": "*",
        "÷": "/",
        "，": ",",
        "、": ",",
        "；": ";",
        "：": ":",
        "（": "(",
        "）": ")",
        "＝": "=",
        "→": "->",
    }
)
_TRUE_WORDS = frozenset({"true", "t", "1", "yes", "y", "对", "正确", "是", "√"})
_FALSE_WORDS = frozenset({"false", "f", "0", "no", "n", "错", "错误", "否", "×"})


@dataclass(frozen=True)
class Judgement:
    """``correct`` 为 None 表示无法自动判定，界面必须提示人工核对。"""

    correct: bool | None
    reason: str = ""

    @property
    def needs_manual_check(self) -> bool:
        """``correct`` 为 None 时为 True，界面据此提示人工核对。"""
        return self.correct is None


def _normalize_raw(text: str) -> str:
    """NFKC 归一并去首尾空白；不做符号替换。"""
    return unicodedata.normalize("NFKC", str(text)).strip()


def normalize_answer(text: str) -> str:
    """把作答归一成可比较形式：NFKC、常见数学符号替换、折叠空白。

    Args:
        text: 原始文本，内部先转成字符串。

    Returns:
        去首尾空白、连续空白压成一个空格的文本。
    """
    return re.sub(r"\s+", " ", _normalize_raw(text).translate(_TRANSLATE)).strip()


def compact_answer(text: str) -> str:
    """在归一化基础上再去掉全部空格，用于选择、填空、找错题。"""
    return normalize_answer(text).replace(" ", "")


def parse_tokens(text: str) -> tuple[str, ...]:
    """把多选、排序、步骤作答拆成 token 元组。

    支持逗号、分号、空白、箭头分隔，也兼容 ``["A", "B"]`` 这类 Python 字面量。

    Args:
        text: 原始作答。

    Returns:
        归一化后的 token 元组；空作答返回空元组。
    """
    raw = normalize_answer(text)
    if raw.startswith("[") and raw.endswith("]"):
        try:
            value = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            value = None
        if isinstance(value, (list, tuple, set)):
            return tuple(
                token
                for token in (normalize_answer(str(item)) for item in value)
                if token
            )
    parts = re.split(r"[,;\s]+|->", raw)
    return tuple(token for token in (normalize_answer(part) for part in parts) if token)


def parse_pairs(text: str) -> dict[str, str] | None:
    """把配对作答解析成“左 → 右”字典。

    支持 ``A=1;B=2``、``A:1,B:2``、``A->1`` 等写法，也兼容字典字面量。
    解析失败，或同一个左值映射到不同右值时返回 None，不猜。

    Args:
        text: 原始作答。

    Returns:
        配对字典；无法可靠解析时为 ``None``。
    """
    raw = normalize_answer(text)
    if raw.startswith("{") and raw.endswith("}"):
        try:
            value = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            value = None
        if isinstance(value, dict):
            return {
                normalize_answer(str(key)): normalize_answer(str(item))
                for key, item in value.items()
            }
    pairs: dict[str, str] = {}
    for item in re.split(r"[,;]", raw):
        item = item.strip()
        if not item:
            continue
        for separator in ("->", "=>", "=", ":", "-"):
            if separator in item:
                left, right = item.split(separator, 1)
                break
        else:
            return None
        left, right = normalize_answer(left), normalize_answer(right)
        if not left or not right:
            return None
        if left in pairs and pairs[left] != right:
            return None
        pairs[left] = right
    return pairs or None


def _as_number(text: str) -> Fraction | None:
    """把作答转成有理数；不可解析或不是有限值时返回 None。"""
    value = normalize_answer(text).replace(" ", "")
    if not value:
        return None
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError):
        try:
            number = float(value)
        except ValueError:
            return None
        return Fraction(number) if math.isfinite(number) else None


def _numbers_close(left: Fraction, right: Fraction) -> bool:
    """数值比较：相对误差 1e-6，绝对误差 1e-9。"""
    return math.isclose(
        float(left), float(right), rel_tol=1e-6, abs_tol=1e-9
    )


def _parse_bool(text: str) -> bool | None:
    """识别 True/False 的中英文与符号写法；无法识别返回 None。"""
    value = _normalize_raw(text).lower()
    if value in _TRUE_WORDS:
        return True
    if value in _FALSE_WORDS:
        return False
    return None


def _judge_choice(exercise: Exercise, answer: str) -> Judgement:
    """选择题：忽略空白后与标准答案或 accepted 精确匹配。"""
    user = compact_answer(answer)
    candidates = (exercise.answer, *exercise.accepted)
    return Judgement(any(user == compact_answer(item) for item in candidates))


def _judge_multi(exercise: Exercise, answer: str) -> Judgement:
    """多选题：集合相等；先比对 accepted，再比对标准答案。"""
    user = set(parse_tokens(answer))
    correct = set(parse_tokens(exercise.answer))
    for alternative in exercise.accepted:
        if user == set(parse_tokens(alternative)):
            return Judgement(True)
    return Judgement(user == correct)


def _judge_truefalse(exercise: Exercise, answer: str) -> Judgement:
    """判断题：任意一侧识别失败都按答错处理。"""
    user = _parse_bool(answer)
    correct = _parse_bool(exercise.answer)
    if user is None or correct is None:
        return Judgement(False)
    return Judgement(user is correct)


def _judge_fill(exercise: Exercise, answer: str) -> Judgement:
    """填空题：先去空白精确匹配，再按数值容差匹配。"""
    user_text = compact_answer(answer)
    candidates = (exercise.answer, *exercise.accepted)
    for candidate in candidates:
        if user_text == compact_answer(candidate):
            return Judgement(True)
    user_number = _as_number(answer)
    if user_number is not None:
        for candidate in candidates:
            correct_number = _as_number(candidate)
            if correct_number is not None and _numbers_close(
                user_number, correct_number
            ):
                return Judgement(True)
    return Judgement(False)


def _judge_expr(exercise: Exercise, answer: str) -> Judgement:
    """表达式题：过白名单后做 sympy 等价判定；无法确认时返回 None。"""
    variables: set[str] = set()
    for candidate in (exercise.answer, *exercise.accepted):
        variables |= expr_variables(candidate)

    reason = validate_expression(answer, variables)
    if reason is not None:
        return Judgement(None, f"表达式未通过安全白名单：{reason}")

    saw_unverified = False
    for candidate in (exercise.answer, *exercise.accepted):
        verdict = are_equivalent(answer, candidate, variables)
        if verdict is SymbolicVerdict.EQUIVALENT:
            return Judgement(True)
        if verdict in (SymbolicVerdict.UNVERIFIED, SymbolicVerdict.REJECTED):
            saw_unverified = True
    if saw_unverified:
        return Judgement(None, "符号验证超时/异常，需人工核对")
    return Judgement(False)


def _sequence_with_one_adjacent_swap(user: tuple[str, ...], correct: tuple[str, ...]) -> bool:
    """设计文档允许“等价相邻”：此处确定性落地为最多一次相邻交换。"""
    if len(user) != len(correct):
        return False
    diff = [index for index in range(len(correct)) if user[index] != correct[index]]
    if len(diff) != 2 or diff[1] != diff[0] + 1:
        return False
    first = diff[0]
    return user[first] == correct[first + 1] and user[first + 1] == correct[first]


def _judge_proof_order(exercise: Exercise, answer: str) -> Judgement:
    """步骤排序：完全一致，或最多一次相邻交换，算答对。"""
    user = parse_tokens(answer)
    correct = parse_tokens(exercise.answer)
    if user == correct:
        return Judgement(True)
    if _sequence_with_one_adjacent_swap(user, correct):
        return Judgement(True)
    for alternative in exercise.accepted:
        if user == parse_tokens(alternative):
            return Judgement(True)
    return Judgement(False)


def _judge_find_error(exercise: Exercise, answer: str) -> Judgement:
    """找错题：忽略空白后与标准答案或 accepted 精确匹配。"""
    user = compact_answer(answer)
    candidates = (exercise.answer, *exercise.accepted)
    return Judgement(any(user == compact_answer(item) for item in candidates))


def _judge_match(exercise: Exercise, answer: str) -> Judgement:
    """配对题：解析成功且与标准或备选完全一致才判对。"""
    user = parse_pairs(answer)
    if user is None:
        return Judgement(False)
    for candidate in (exercise.answer, *exercise.accepted):
        correct = parse_pairs(candidate)
        if correct is not None and user == correct:
            return Judgement(True)
    return Judgement(False)


# 题型 → 判定函数；evaluate 只做分派
_JUDGES = {
    ExerciseKind.CHOICE: _judge_choice,
    ExerciseKind.MULTI: _judge_multi,
    ExerciseKind.TRUEFALSE: _judge_truefalse,
    ExerciseKind.FILL: _judge_fill,
    ExerciseKind.EXPR: _judge_expr,
    ExerciseKind.PROOF_ORDER: _judge_proof_order,
    ExerciseKind.FIND_ERROR: _judge_find_error,
    ExerciseKind.MATCH: _judge_match,
}


def evaluate(exercise: Exercise, answer: str) -> Judgement:
    """按题型分派判定，返回可区分“答错”和“需人工核对”的结果。

    Args:
        exercise: 题目，``kind`` 决定使用哪个判定器。
        answer: 学生原始作答，内部按题型归一化。

    Returns:
        ``Judgement``；``correct`` 为 None 表示无法自动核对，界面必须提示人工检查。

    Raises:
        NotImplementedError: ``exercise.kind`` 没有对应判定器。
    """
    try:
        return _JUDGES[exercise.kind](exercise, answer)
    except KeyError:
        raise NotImplementedError(f"{exercise.kind} 判定器未实现") from None


def judge(exercise: Exercise, answer: str) -> bool:
    """兼容 M1 的布尔接口；无法自动核对时按“未答对”处理。"""
    return evaluate(exercise, answer).correct is True
