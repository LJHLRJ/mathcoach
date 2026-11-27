"""写操作红线：同意校验、逐次确认、禁止写入仓库、脱敏与摘要。

纯函数 + 显式异常，不 import Streamlit；观察状态由 UI 层传入。
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from ..domain.models import Consent

FULL_CONFIRMATION = "我确认执行此操作"

# 授权范围内的常规写入：consent 已开启时自动执行。
ROUTINE_OPS: dict[str, str | None] = {
    "receipt": "memory",
    "mistake": "mistake_book",
    "review": "mistake_book",
    "daily": "memory",
    "challenge": "memory",
    "profile": None,
    "consent": None,
}
# 导出、GitHub、打包等必须逐次确认。
CONFIRMATION_OPS = frozenset(
    {"export", "batch_export", "github_draft", "github_write", "package", "download", "task_file"}
)
FORBIDDEN_DESTINATIONS = frozenset({"repo", "workspace", "git", "pages", "repository"})

_SENSITIVE_KEYS = frozenset(
    {"token", "api_key", "apikey", "password", "secret", "authorization"}
)


class WriteBlocked(Exception):
    """写操作被红线拒绝。

    Attributes:
        reason: 机器可读的分类。
    """

    def __init__(self, reason: str) -> None:
        """记录拒绝原因。"""
        super().__init__(reason)
        self.reason = reason


class ConfirmationRequired(Exception):
    """高风险操作缺少逐次确认。

    Attributes:
        reason: 机器可读的分类。
    """

    def __init__(self, reason: str = "confirmation_required") -> None:
        """记录需要确认的原因。"""
        super().__init__(reason)
        self.reason = reason


def sanitize_text(text: str) -> str:
    """脱敏文本。

    覆盖 Token、手机号、身份证、内网地址，以及字段上下文里的姓名与住址。

    Args:
        text: 原始文本。

    Returns:
        脱敏后的文本；空串原样返回。
    """
    if not text:
        return text
    text = re.sub(
        r"(?i)\bauthorization\s*[:=]\s*bearer\s+\S+",
        "authorization=[已脱敏]",
        text,
    )
    text = re.sub(
        r"(?i)\b(api[_-]?key|token|password|secret|authorization)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[已脱敏]",
        text,
    )
    text = re.sub(r"\b\d{17}[\dXx]\b", "[已脱敏]", text)
    text = re.sub(r"\b1[3-9]\d{9}\b", "[已脱敏]", text)
    text = re.sub(r"\b\d{3,4}-\d{7,8}\b", "[已脱敏]", text)
    text = re.sub(
        r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[已脱敏]", text
    )
    text = re.sub(r"\b192\.168\.\d{1,3}\.\d{1,3}\b", "[已脱敏]", text)
    text = re.sub(
        r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b", "[已脱敏]", text
    )
    text = re.sub(
        r"\b[a-zA-Z0-9.-]+\.(?:internal|local|intranet)\b", "[已脱敏]", text
    )
    text = re.sub(
        r"(?P<label>姓名|联系人|name)\s*[:=：]\s*[^\s,，;；]+",
        r"\g<label>=[已脱敏]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?P<label>住址|地址|小区|门牌)\s*[:=：]?\s*[^\n,，;；]+",
        r"\g<label>=[已脱敏]",
        text,
    )
    return text


def sanitize_payload(payload: Any) -> Any:
    """递归脱敏映射、列表与字符串。

    键名命中 ``_SENSITIVE_KEYS`` 时整项替换为 ``[已脱敏]``，
    其他键继续向下处理；元组转成列表。
    """
    if isinstance(payload, Mapping):
        cleaned = {}
        for key, value in payload.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                cleaned[key] = "[已脱敏]"
            else:
                cleaned[key] = sanitize_payload(value)
        return cleaned
    if isinstance(payload, (list, tuple)):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_text(payload)
    return payload


def describe_write(op: str, payload: Mapping[str, Any] | None = None) -> str:
    """生成写入前摘要，任何字段值都先脱敏。

    Args:
        op: 操作名。
        payload: 写入内容。

    Returns:
        单行摘要，最长 500 字符。
    """
    body = json.dumps(
        sanitize_payload(payload or {}), ensure_ascii=False, default=str
    )
    return sanitize_text(f"{op} · {body}")[:500]


def assert_write_allowed(
    op: str,
    *,
    consent: Consent,
    observed: bool = False,
    confirmation: str | None = None,
    destination: str = "memory",
) -> None:
    """统一写入门。

    依次检查目标位置、操作白名单、授权开关与显式确认。

    Args:
        op: 操作名。
        consent: 当前授权状态。
        observed: 观察状态；保留在契约里，当前不参与判定。
        confirmation: 逐次确认文本。
        destination: 目标位置。

    Raises:
        WriteBlocked: 目标被禁止、操作未知或授权不足。
        ConfirmationRequired: 高风险操作缺少显式确认。
    """
    if destination.lower() in FORBIDDEN_DESTINATIONS:
        raise WriteBlocked("forbidden_destination")
    if op not in ROUTINE_OPS and op not in CONFIRMATION_OPS:
        raise WriteBlocked("unknown_op")

    if op in ROUTINE_OPS:
        required = ROUTINE_OPS[op]
        if required == "memory" and not consent.memory:
            raise WriteBlocked("consent_memory_off")
        if required == "mistake_book" and not consent.mistake_book:
            raise WriteBlocked("consent_mistake_book_off")
        # 例外：授权范围内的收据/错题本写入自动执行，不逐次确认。
        return

    if not (consent.memory or consent.mistake_book):
        raise WriteBlocked("consent_all_off")
    if confirmation != FULL_CONFIRMATION:
        raise ConfirmationRequired("explicit_confirmation_required")
