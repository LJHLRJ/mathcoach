"""应用设置：纯数据模型、校验与不包含密钥的导出序列化。"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dt_time
from typing import Any

from ..safety.redlines import sanitize_text
from .models import AuditEntry, MistakeEntry, Receipt, ReviewItem

DEFAULT_DAILY_REVIEW_LIMIT = 0
MAX_DAILY_REVIEW_LIMIT = 999
DEFAULT_NEW_REVIEW_RATIO = 0
SCHEDULER_MODES = frozenset({"fsrs", "sm2"})
FONT_SIZES = frozenset({"small", "medium", "large"})
THEME_MODES = frozenset({"light", "dark", "system"})
SETTINGS_EXPORT_KEYS = frozenset({"ai_enabled", "daily_review_limit"})


def _parse_bool(value: object) -> bool:
    """严格解析布尔值；无法识别时返回 False。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    return False


@dataclass(frozen=True)
class AppSettings:
    """界面可见设置；API 密钥等敏感值不进入此模型。

    Attributes:
        ai_enabled: 是否启用在线模型；关闭时走离线模板。
        daily_review_limit: 每日复习上限，0 表示不限制。
        new_review_ratio: 新卡占比 0–100。
        scheduler: 调度器，``fsrs`` 或 ``sm2``。
        font_size: 字号，``small`` / ``medium`` / ``large``。
        theme: 主题，``light`` / ``dark`` / ``system``。
        reminder_enabled: 是否开启复习提醒。
        reminder_time: 提醒时间，ISO 时间字符串。
    """

    ai_enabled: bool = False
    daily_review_limit: int = DEFAULT_DAILY_REVIEW_LIMIT
    new_review_ratio: int = DEFAULT_NEW_REVIEW_RATIO
    scheduler: str = "fsrs"
    font_size: str = "medium"
    theme: str = "light"
    reminder_enabled: bool = False
    reminder_time: str = "08:00"

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> AppSettings:
        """从 JSON 映射恢复设置。

        数值截断到合法区间，枚举值不在白名单时回落默认值，
        ``reminder_time`` 解析失败也回落 ``08:00``。布尔值只认
        true/false 及常见等价写法，无法识别时按 False 处理。

        Args:
            values: 设置映射，None 视为空。

        Returns:
            ``AppSettings``。
        """
        data = values or {}
        try:
            limit = int(data.get("daily_review_limit", DEFAULT_DAILY_REVIEW_LIMIT))
        except (TypeError, ValueError):
            limit = DEFAULT_DAILY_REVIEW_LIMIT
        limit = max(0, min(MAX_DAILY_REVIEW_LIMIT, limit))
        try:
            ratio = int(data.get("new_review_ratio", DEFAULT_NEW_REVIEW_RATIO))
        except (TypeError, ValueError):
            ratio = DEFAULT_NEW_REVIEW_RATIO
        ratio = max(0, min(100, ratio))
        scheduler = str(data.get("scheduler", "fsrs")).lower()
        if scheduler not in SCHEDULER_MODES:
            scheduler = "fsrs"
        font_size = str(data.get("font_size", "medium")).lower()
        if font_size not in FONT_SIZES:
            font_size = "medium"
        theme = str(data.get("theme", "light")).lower()
        if theme not in THEME_MODES:
            theme = "light"
        reminder_time = str(data.get("reminder_time", "08:00"))
        try:
            dt_time.fromisoformat(reminder_time)
        except ValueError:
            reminder_time = "08:00"
        return cls(
            ai_enabled=_parse_bool(data.get("ai_enabled", False)),
            daily_review_limit=limit,
            new_review_ratio=ratio,
            scheduler=scheduler,
            font_size=font_size,
            theme=theme,
            reminder_enabled=_parse_bool(data.get("reminder_enabled", False)),
            reminder_time=reminder_time,
        )

    def to_mapping(self, *, include_advanced: bool = False) -> dict[str, Any]:
        """序列化为 settings 表映射。

        Args:
            include_advanced: 是否一并写入新卡占比、调度器、外观与提醒字段。

        Returns:
            可直接写入 settings 表的字典。
        """
        data: dict[str, Any] = {
            "ai_enabled": self.ai_enabled,
            "daily_review_limit": self.daily_review_limit,
        }
        if include_advanced:
            data.update(
                {
                    "new_review_ratio": self.new_review_ratio,
                    "scheduler": self.scheduler,
                    "font_size": self.font_size,
                    "theme": self.theme,
                    "reminder_enabled": self.reminder_enabled,
                    "reminder_time": self.reminder_time,
                }
            )
        return data


def settings_for_export(
    values: AppSettings | Mapping[str, Any] | None,
) -> dict[str, Any]:
    """只保留允许导出的设置字段，其他字段与密钥一律丢弃。

    Args:
        values: 设置对象或原始映射。

    Returns:
        仅含 ``ai_enabled`` 与 ``daily_review_limit`` 的字典。
    """
    if isinstance(values, AppSettings):
        data = values.to_mapping()
    else:
        data = AppSettings.from_mapping(values).to_mapping()
    return {key: data[key] for key in SETTINGS_EXPORT_KEYS}


def _safe(value: object) -> str:
    """转字符串并做敏感词脱敏。"""
    return sanitize_text(str(value))


def _iso(value: datetime) -> str:
    """时间转 ISO 字符串。"""
    return value.isoformat()


def _receipt_row(receipt: Receipt) -> dict[str, Any]:
    """把收据拍平成导出字段，文本字段脱敏。"""
    return {
        "created_at": _iso(receipt.created_at),
        "card_id": receipt.card_id,
        "course": _safe(receipt.course),
        "exercise_type": receipt.exercise_type.value,
        "duration_s": receipt.duration_s,
        "max_hint_level": receipt.max_hint_level,
        "independence": receipt.independence.value,
        "goal": _safe(receipt.goal),
        "basis": _safe(receipt.basis),
    }


def _mistake_row(mistake: MistakeEntry) -> dict[str, Any]:
    """把错题拍平成导出字段，文本字段脱敏。"""
    return {
        "created_at": _iso(mistake.created_at),
        "exercise_id": mistake.exercise_id,
        "card_id": mistake.card_id,
        "course": _safe(mistake.course),
        "exercise_type": mistake.exercise_type.value,
        "stem": _safe(mistake.stem),
        "user_answer": _safe(mistake.user_answer),
        "correct_answer": _safe(mistake.correct_answer),
        "error_type": mistake.error_type.value,
        "max_hint_level": mistake.max_hint_level,
        "review_state": mistake.review_state.value,
        "review_count": mistake.review_count,
        "consecutive_correct": mistake.consecutive_correct,
    }


def _review_row(item: ReviewItem) -> dict[str, Any]:
    """把待复习项拍平成导出字段，题干脱敏。"""
    return {
        "exercise_id": item.mistake.exercise_id,
        "card_id": item.mistake.card_id,
        "due_at": _iso(item.due_at),
        "stem": _safe(item.mistake.stem),
    }


def export_json(
    *,
    receipts: Iterable[Receipt],
    mistakes: Iterable[MistakeEntry],
    review_items: Iterable[ReviewItem],
    settings: AppSettings | Mapping[str, Any] | None,
    now: datetime,
) -> str:
    """生成完整学习数据 JSON，不含任何密钥。

    Args:
        receipts: 收据。
        mistakes: 错题。
        review_items: 待复习项。
        settings: 设置对象或原始映射。
        now: 导出时间。

    Returns:
        缩进 2 空格的 JSON 文本。
    """
    payload = {
        "generated_at": _iso(now),
        "settings": settings_for_export(settings),
        "receipts": [_receipt_row(receipt) for receipt in receipts],
        "mistakes": [_mistake_row(mistake) for mistake in mistakes],
        "review_queue": [_review_row(item) for item in review_items],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


RECEIPT_CSV_FIELDS = (
    "created_at",
    "card_id",
    "course",
    "exercise_type",
    "duration_s",
    "max_hint_level",
    "independence",
    "goal",
    "basis",
)
MISTAKE_CSV_FIELDS = (
    "created_at",
    "exercise_id",
    "card_id",
    "course",
    "exercise_type",
    "stem",
    "user_answer",
    "correct_answer",
    "error_type",
    "max_hint_level",
    "review_state",
    "review_count",
    "consecutive_correct",
)


def _to_csv(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    """按字段顺序写 CSV 文本，含表头。"""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def export_receipts_csv(receipts: Iterable[Receipt]) -> str:
    """生成收据 CSV，文本字段经过脱敏。"""
    return _to_csv([_receipt_row(receipt) for receipt in receipts], RECEIPT_CSV_FIELDS)


def export_mistakes_csv(mistakes: Iterable[MistakeEntry]) -> str:
    """生成错题本 CSV，文本字段经过脱敏。"""
    return _to_csv([_mistake_row(mistake) for mistake in mistakes], MISTAKE_CSV_FIELDS)


def _md(value: object) -> str:
    """脱敏后转义表格竖线与换行，供 Markdown 表格使用。"""
    return _safe(value).replace("|", r"\|").replace("\n", " ").strip()


def export_markdown(
    *,
    receipts: Iterable[Receipt],
    mistakes: Iterable[MistakeEntry],
    settings: AppSettings | Mapping[str, Any] | None,
    now: datetime,
) -> str:
    """生成 Markdown 学习报告，不含任何密钥。

    报告含概览、收据列表与错题列表；文本字段先脱敏再转义表格字符。

    Args:
        receipts: 收据。
        mistakes: 错题。
        settings: 设置对象或原始映射。
        now: 生成时间。

    Returns:
        Markdown 文本。
    """
    receipt_list = list(receipts)
    mistake_list = list(mistakes)
    exported = settings_for_export(settings)
    lines = [
        "# 数学陪练学习报告",
        "",
        f"生成时间：{_iso(now)}",
        "",
        "## 概览",
        f"- 收据：{len(receipt_list)} 条",
        f"- 错题：{len(mistake_list)} 条",
        f"- 每日复习上限：{exported['daily_review_limit']}（0 表示不限制）",
        f"- AI 模式：{'开启' if exported['ai_enabled'] else '关闭（离线模板）'}",
        "",
        "## 收据",
        "",
    ]
    if not receipt_list:
        lines.append("暂无收据。")
    else:
        for receipt in receipt_list:
            lines.append(
                f"- {_iso(receipt.created_at)} · {_md(receipt.course)} · "
                f"{receipt.exercise_type.value} · L{receipt.max_hint_level} · "
                f"{receipt.independence.value} · {receipt.duration_s} 秒"
            )
    lines.extend(["", "## 错题", ""])
    if not mistake_list:
        lines.append("暂无错题。")
    else:
        for mistake in mistake_list:
            lines.append(
                f"- {_md(mistake.stem)} · {mistake.error_type.value} · "
                f"{mistake.review_state.value}"
            )
    lines.append("")
    return "\n".join(lines)


AUDIT_CSV_FIELDS = ("id", "created_at", "op", "result")


def export_audit_csv(entries: Iterable[AuditEntry]) -> str:
    """导出只读审计日志 CSV，结果字段经过脱敏。"""
    rows = [
        {
            "id": entry.id,
            "created_at": _iso(entry.created_at),
            "op": _safe(entry.op),
            "result": _safe(entry.result),
        }
        for entry in entries
    ]
    return _to_csv(rows, AUDIT_CSV_FIELDS)


def export_audit_json(entries: Iterable[AuditEntry], now: datetime) -> str:
    """导出审计日志 JSON，结果字段经过脱敏。

    Args:
        entries: 审计记录。
        now: 导出时间。

    Returns:
        缩进 2 空格的 JSON 文本。
    """
    payload = {
        "generated_at": _iso(now),
        "audit": [
            {
                "id": entry.id,
                "created_at": _iso(entry.created_at),
                "op": _safe(entry.op),
                "result": _safe(entry.result),
            }
            for entry in entries
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
