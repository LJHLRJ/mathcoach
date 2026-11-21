"""混合复习包纯函数：到期 3 + 先修缺口 1 + 拓展 1，缺口优先。"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

DUE_QUOTA = 3
GAP_QUOTA = 1
VARIANT_QUOTA = 1
DEFAULT_TOTAL = 5


def compose(
    due: Sequence[T],
    gaps: Sequence[T],
    variants: Sequence[T],
    total: int = DEFAULT_TOTAL,
) -> list[T]:
    """按固定配额组合并去重；不足时依次用到到期、拓展、缺口补齐。"""
    if total <= 0:
        return []

    result: list[T] = []

    def add(item: T) -> bool:
        if item in result:
            return False
        result.append(item)
        return True

    # 先修缺口固定 1 题，并放在最前面
    for item in gaps[:GAP_QUOTA]:
        add(item)

    # 到期题固定 3 题
    due_added = 0
    for item in due:
        if due_added >= DUE_QUOTA or len(result) >= total:
            break
        if add(item):
            due_added += 1

    # 拓展固定 1 题
    if len(result) < total:
        for item in variants[:VARIANT_QUOTA]:
            add(item)

    # 配额不足时用到期题优先补齐，再补拓展/缺口
    for pool in (due, variants, gaps):
        if len(result) >= total:
            break
        for item in pool:
            if len(result) >= total:
                break
            add(item)

    return result[:total]
