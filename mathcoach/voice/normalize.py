"""语音转写规范化：把口语回答整理成追问判定可读的数学文本。

只做文本归一，不做判定；规范化后的文本仍走现有的
``judge_follow_up``，不修改判定阈值，也不触碰 ``verify/``。

规则保持保守：
- 去掉“嗯/就是/然后”等填充词；
- 中文数字、分数、根号、三角函数口语转成常见写法；
- 未识别的中文保持原样，避免误改题意。
"""
from __future__ import annotations

import re
import unicodedata

_CN_DIGITS = "零一二三四五六七八九十百千万两"
_DIGIT_VALUES = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_UNIT_VALUES = {"十": 10, "百": 100, "千": 1000, "万": 10000}

_FILLERS = re.compile(r"嗯|呃|唔|那个|就是说|然后呢|然后")
_TAIL_PARTICLES = re.compile(r"等于吧|吧|呢|呀|啊")
_FRACTION = re.compile(
    rf"([{_CN_DIGITS}]+|派|π)分之"
    rf"([{_CN_DIGITS}]+|派|π|根号[{_CN_DIGITS}]+)"
)
_SQRT_CN = re.compile(rf"根号([{_CN_DIGITS}]+)")
_CN_AFTER_TRIGGER = re.compile(
    rf"(?<=等于)([{_CN_DIGITS}]+)|(?<=是)([{_CN_DIGITS}]+)|"
    rf"(?<=为)([{_CN_DIGITS}]+)|(?<=得)([{_CN_DIGITS}]+)"
)
_SQUARE_TRIG = re.compile(r"(sin|cos|tan)\s*平方\s*([a-z])")
_SQUARE_VAR = re.compile(r"([a-z])\s*的?平方")
_OP_WORDS = {
    "乘以": "*",
    "除以": "/",
    "加上": "+",
    "减去": "-",
}


def _cn_to_int(text: str) -> int:
    """中文数字转整数；无法解析时返回 0。"""
    if not text:
        return 0
    if "万" in text:
        high, _, low = text.partition("万")
        return _cn_to_int(high) * 10000 + _cn_to_int(low)
    total = 0
    number = 0
    for char in text:
        if char in _DIGIT_VALUES:
            number = _DIGIT_VALUES[char]
            continue
        unit = _UNIT_VALUES.get(char)
        if unit is None or unit == 10000:
            continue
        if number == 0:
            number = 1
        total += number * unit
        number = 0
    return total + number


def _atom(token: str) -> str:
    """把分母/分子 token 转成数学写法。"""
    if token in ("派", "π"):
        return "π"
    if token.startswith("根号"):
        return f"sqrt({_cn_to_int(token[2:])})"
    return str(_cn_to_int(token))


def _fraction_replacement(match: re.Match[str]) -> str:
    """把“X分之Y”转成 Y/X。"""
    denominator = _atom(match.group(1))
    numerator = _atom(match.group(2))
    return f"{numerator}/{denominator}"


def normalize_spoken_math(text: str) -> str:
    """规范化一段语音转写文本；空输入返回空串。"""
    if not text or not text.strip():
        return ""
    value = unicodedata.normalize("NFKC", text).lower()
    value = value.translate(
        str.maketrans(
            {
                "×": "*",
                "÷": "/",
                "−": "-",
                "－": "-",
                "＋": "+",
                "＝": "=",
            }
        )
    )
    value = _FILLERS.sub("", value)
    value = _TAIL_PARTICLES.sub("", value)
    value = re.sub(r"[,，、]{2,}", "，", value).strip("，,")
    value = _FRACTION.sub(_fraction_replacement, value)
    value = _SQUARE_TRIG.sub(r"\1^2(\2)", value)
    value = _SQUARE_VAR.sub(r"\1^2", value)
    value = _SQRT_CN.sub(
        lambda match: f"sqrt({_cn_to_int(match.group(1))})", value
    )
    value = _CN_AFTER_TRIGGER.sub(
        lambda match: str(_cn_to_int(match.group(0))), value
    )
    value = value.replace("派", "π").replace("圆周率", "π")
    for word, symbol in _OP_WORDS.items():
        value = re.sub(
            rf"(?<=[0-9a-zπ)])\s*{word}\s*(?=[0-9a-zπ(])",
            symbol,
            value,
        )
    value = re.sub(r"(?<=[0-9a-zπ)])\s*加\s*(?=[0-9a-zπ(])", "+", value)
    value = re.sub(r"(?<=[0-9a-zπ)])\s*减\s*(?=[0-9a-zπ(])", "-", value)
    return re.sub(r"\s+", "", value)
