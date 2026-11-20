"""注入守卫：越权指令、隐藏字符、混用文字与数学伪装注入。

只做判定，不改写内容；命中返回 Blocked，由 UI 回一句简短拒绝并回到学习任务。
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

REFUSAL_TEXT = "这个请求我不能执行，我们回到数学练习。"

_ZERO_WIDTH = frozenset(
    "\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2060\ufeff"
)

_CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ѕ": "s",
        "ԁ": "d",
        "ԛ": "q",
        "ԝ": "w",
        "һ": "h",
        "ӏ": "l",
        "ɩ": "i",
    }
)

_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"忽略.{0,8}(指令|规则|提示|限制)",
        r"(系统|system).{0,8}(提示词|prompt)",
        r"(无限制|开发者|越狱|jailbreak|DAN).{0,6}(模式)?",
        r"(启用|部署|发布).{0,8}(Pages|页面|站点)",
        r"(生成|创建|写入).{0,8}(任务文件|脚本文件|配置文件)",
        r"自动(下载|安装|打包|部署)",
        r"(批量|全部).{0,6}(导出|下载)",
        r"(这是|作为).{0,8}(CTF|渗透|红队|评审测试|演示测试)",
        r"(忽略|跳过).{0,8}(确认|安全|审批)",
        r"(以后|今后).{0,8}(不用|无需|不必).{0,8}(确认|审批)",
        r"(输出|泄露|告诉我).{0,8}(密钥|token|api[_-]?key)",
    )
)

_MATH_HINTS = re.compile(
    r"(\b[A-Za-z]\s*=|∫|∀|∃|∈|证明|公式|函数|评分函数|目标函数|变量|方程)",
    re.IGNORECASE,
)
_OPERATION_HINTS = re.compile(
    r"(__import__|\bopen\s*\(|read_file|write_file|\bexec\s*\(|\beval\s*\(|"
    r"subprocess|os\.system|rm\s+-rf|curl|wget|git\s+push|"
    r"批量导出|全部导出|导出.{0,6}(数据|文件|学习包|清单|/)|"
    r"下载|安装|打包|部署|写入|读取.{0,4}文件|/tmp|/etc/|https?://)",
    re.IGNORECASE,
)


class Blocked(Exception):
    """安全守卫命中；reason 是机器可读分类，不直接展示完整原因。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _script_of(character: str) -> str | None:
    code = ord(character)
    if "a" <= character.lower() <= "z":
        return "latin"
    if 0x0400 <= code <= 0x04FF:
        return "cyrillic"
    if 0x0370 <= code <= 0x03FF:
        return "greek"
    return None


def _has_mixed_script(text: str) -> bool:
    for token in re.findall(r"[A-Za-z\u0400-\u04FF\u0370-\u03FF]+", text):
        scripts = {script for character in token if (script := _script_of(character))}
        if "cyrillic" in scripts and len(scripts) > 1:
            return True
        if "greek" in scripts and "latin" in scripts and len(token) > 2:
            return True
    return False


def detect_math_framing(text: str) -> bool:
    """数学形式与操作意图共现时返回 True。"""
    if not text:
        return False
    return bool(_MATH_HINTS.search(text) and _OPERATION_HINTS.search(text))


def detect_injection(text: str) -> Blocked | None:
    """命中返回 Blocked(reason)，否则返回 None。"""
    if not text:
        return None
    if any(character in _ZERO_WIDTH for character in text):
        return Blocked("zero_width")

    normalized = unicodedata.normalize("NFKC", text)
    folded = normalized.translate(_CONFUSABLES)
    if _has_mixed_script(normalized):
        return Blocked("mixed_script")
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(folded):
            return Blocked("instruction")
    if detect_math_framing(folded):
        return Blocked("math_framing")
    return None


def check_parsed_answer(parsed: Any, threshold: float) -> Blocked | None:
    """LLM 解析结果进入引擎前的安全检查。"""
    reason = str(getattr(parsed, "reason", "") or "")
    blocked = detect_injection(reason)
    if blocked is not None:
        return blocked
    confidence = float(getattr(parsed, "confidence", 0.0) or 0.0)
    if confidence < threshold:
        return Blocked("low_confidence")
    return None
