"""智能复习包：优先到期错题，不足 5 题时用同课程练习补齐。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.models import KnowledgeCard
from ..session.daily import DailyQuestion
from ..timeutil import end_of_local_day
from .repository import Repository
from .scheduler import build_review_pack

REVIEW_PACKAGE_SIZE = 5
REVIEW_PACKAGE_LIMIT_S = 900


@dataclass(frozen=True)
class ReviewPackage:
    questions: tuple[DailyQuestion, ...]
    reason: str


def build_review_package(
    repository: Repository,
    cards: list[KnowledgeCard],
    now: datetime,
    count: int = REVIEW_PACKAGE_SIZE,
    priority_card_ids: set[str] | None = None,
    new_ratio: int = 0,
) -> ReviewPackage:
    items = repository.list_review_items()
    if not items and not priority_card_ids and new_ratio <= 0:
        return ReviewPackage((), "暂无待复习错题，先完成一次小测。")

    today_end = end_of_local_day(now)
    priority = priority_card_ids or set()
    selected = build_review_pack(
        repository,
        cards,
        now,
        priority,
        count,
        new_ratio=new_ratio,
    )
    due_count = sum(1 for item in items if item.due_at <= today_end)
    prefix = (
        f"从 {len(items)} 道待复习错题中生成混合复习包"
        if items
        else "按新卡占比生成混合复习包"
    )
    reason = (
        f"{prefix}：新卡占比 {new_ratio}%，"
        f"到期 {due_count} 题、先修缺口 {len(priority)} 题，"
        f"共 {len(selected)} 题。"
    )
    return ReviewPackage(tuple(selected), reason)
