"""应用设置：纯数据模型、校验与不包含密钥的导出序列化。"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..safety.redlines import sanitize_text
from .models import MistakeEntry, Receipt, ReviewItem

DEFAULT_DAILY_REVIEW_LIMIT = 0
MAX_DAILY_REVIEW_LIMIT = 999
DEFAULT_NEW_REVIEW_RATIO = 50
SCHEDULER_MODES = frozenset({"fsrs", "sm2"})
FONT_SIZES = frozenset({"small", "medium", "large"})
SETTINGS_EXPORT_KEYS = frozenset({"ai_enabled", "daily_review_limit"})


@dataclass(frozen=True)
class AppSettings:
    """用户可见设置；API 密钥等敏感值不进入此模型。"""

    ai_enabled: bool = False
    daily_review_limit: int = DEFAULT_DAILY_REVIEW_LIMIT
    new_review_ratio: int = DEFAULT_NEW_REVIEW_RATIO
    scheduler: str = "fsrs"
    font_size: str = "medium"

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> AppSettings:
        """从 JSON 映射恢复设置；非法数值回落到安全默认值。"""
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
        return cls(
            ai_enabled=bool(data.get("ai_enabled", False)),
            daily_review_limit=limit,
            new_review_ratio=ratio,
            scheduler=scheduler,
            font_size=font_size,
        )

    def to_mapping(self, *, include_advanced: bool = False) -> dict[str, Any]:
        """序列化为 settings 表映射；P1 字段可按需一并写入。"""
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
                }
            )
        return data


def settings_for_export(
    values: AppSettings | Mapping[str, Any] | None,
) -> dict[str, Any]:
    """仅返回允许导出的设置字段，未知字段与密钥一律丢弃。"""
    if isinstance(values, AppSettings):
        data = values.to_mapping()
    else:
        data = AppSettings.from_mapping(values).to_mapping()
    return {key: data[key] for key in SETTINGS_EXPORT_KEYS}


def _safe(value: object) -> str:
    return sanitize_text(str(value))


def _iso(value: datetime) -> str:
    return value.isoformat()


def _receipt_row(receipt: Receipt) -> dict[str, Any]:
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
    """生成不含密钥的完整 JSON 学习数据导出。"""
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
    return _safe(value).replace("|", r"\|").replace("\n", " ").strip()


def export_markdown(
    *,
    receipts: Iterable[Receipt],
    mistakes: Iterable[MistakeEntry],
    settings: AppSettings | Mapping[str, Any] | None,
    now: datetime,
) -> str:
    """生成不包含密钥的 Markdown 学习报告。"""
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
