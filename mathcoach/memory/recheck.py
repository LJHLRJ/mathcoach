"""记忆跨会话投毒复核：写入前先判断记忆条目是否可信。"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

MIN_INDEPENDENT_EVIDENCE = 2

_OVERRIDE_PATTERNS = re.compile(
    r"(不用|无需|不必|跳过|绕过).{0,8}(确认|审批|安全)|"
    r"(永久允许|以后直接|忽略规则|直接执行)",
    re.IGNORECASE,
)
_CONTRADICTION_PATTERNS = re.compile(
    r"(推翻|错误|不成立|与事实不符|伪造|不准确)", re.IGNORECASE
)


@dataclass(frozen=True)
class RecheckResult:
    """记忆条目的复核结果。

    Attributes:
        allowed: 是否允许写入。
        status: ``通过`` / ``待复核`` / ``拒绝``。
        reason: 说明。
    """

    allowed: bool
    status: str
    reason: str


def _as_text(value: Any) -> str:
    """把字符串、映射或其他值摊平成一段文本。"""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return " ".join(str(item) for item in value.values()).strip()
    return str(value).strip()


def _evidence_texts(evidence: Sequence[Any] | None) -> list[str]:
    """把独立证据摊平成非空文本列表。"""
    if evidence is None:
        return []
    if isinstance(evidence, (str, Mapping)):
        evidence = [evidence]
    return [text for item in evidence if (text := _as_text(item))]


def recheck_decision(
    memory_entry: Any, independent_evidence: Sequence[Any] | None = None
) -> RecheckResult:
    """复核记忆条目是否可信。

    记忆里出现绕过确认、永久允许一类说法时转待复核；独立证据与记忆冲突
    时拒绝；证据少于 2 条转待复核；其余通过。与记忆相同的证据不计入。

    Args:
        memory_entry: 待写入的记忆内容，字符串或映射。
        independent_evidence: 独立证据，字符串、映射或它们的序列。

    Returns:
        ``RecheckResult``。
    """
    memory_text = _as_text(memory_entry)
    if _OVERRIDE_PATTERNS.search(memory_text):
        return RecheckResult(False, "待复核", "记忆条目试图绕过确认流程")

    evidence = [
        text
        for text in _evidence_texts(independent_evidence)
        if text and text != memory_text
    ]
    if any(_CONTRADICTION_PATTERNS.search(text) for text in evidence):
        return RecheckResult(False, "拒绝", "独立证据与记忆内容冲突")
    if len(evidence) < MIN_INDEPENDENT_EVIDENCE:
        return RecheckResult(False, "待复核", "独立证据不足，至少需要 2 条")
    return RecheckResult(True, "通过", "独立证据充分且未发现冲突")
