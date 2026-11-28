"""页面内只读快照：每轮渲染只取一次全量，供多个聚合复用。"""
from __future__ import annotations

from typing import Any

from ..domain.models import MistakeEntry, Receipt, ReviewItem, ReviewState
from ..memory.repository import Repository


class RepositorySnapshot:
    """把同一轮渲染中的全量读取合并为一次。

    只重写仪表盘与周报会用到的三个列表读取；其余方法原样委托给仓储。
    快照只活在当前脚本运行内，不跨 rerun 缓存，避免展示过期数据。
    """

    def __init__(self, repository: Repository) -> None:
        self._repository = repository
        self._receipts = tuple(repository.list_receipts(limit=None))
        self._mistakes = tuple(repository.list_mistakes(limit=None))
        self._review_items = tuple(repository.list_review_items())
        self._mastery: dict[str, float | None] = {}

    def list_receipts(self, limit: int | None = 50) -> list[Receipt]:
        """按快照返回收据；``limit=None`` 返回全部。"""
        items = list(self._receipts)
        return items if limit is None else items[:limit]

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]:
        """按快照返回错题，可过滤已掌握条目。"""
        items = [
            entry
            for entry in self._mistakes
            if include_mastered
            or entry.review_state is not ReviewState.MASTERED
        ]
        return items if limit is None else items[:limit]

    def list_review_items(self) -> list[ReviewItem]:
        """返回快照中的待复习项。"""
        return list(self._review_items)

    def get_mastery(self, card_id: str) -> float | None:
        """按卡片惰性读取掌握概率，同一轮内只查一次。"""
        if card_id not in self._mastery:
            self._mastery[card_id] = self._repository.get_mastery(card_id)
        return self._mastery[card_id]

    def __getattr__(self, name: str) -> Any:
        """未重写的方法委托给原仓储，保持接口兼容。"""
        return getattr(self._repository, name)
