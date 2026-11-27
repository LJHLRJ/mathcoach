"""混合复习包纯函数：先修缺口 1 + 错题变式 1 固定，其余按新卡占比分配。"""
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
    new: Sequence[T] = (),
    new_ratio: int = 0,
) -> list[T]:
    """按配额组合复习包并去重。

    先修缺口固定 1 题且排在最前；错题变式固定 1 题；剩余题位按 ``new_ratio``
    在到期题与新卡之间分配，比例四舍五入。配额不足时依次用到期题、变式、
    缺口、新卡补齐，最后截到 ``total``。

    Args:
        due: 到期复习题，按优先级传入。
        gaps: 先修缺口题。
        variants: 错题变式题。
        total: 总题数，≤ 0 时返回空列表。
        new: 新卡题。
        new_ratio: 新卡占比 0–100，越界会被截断。

    Returns:
        去重后的题目列表，长度不超过 ``total``。
    """
    if total <= 0:
        return []

    ratio = max(0, min(100, int(new_ratio)))
    flexible = max(total - GAP_QUOTA - VARIANT_QUOTA, 0)
    new_quota = int(flexible * ratio / 100 + 0.5)
    due_quota = flexible - new_quota

    result: list[T] = []

    def add(item: T) -> bool:
        """去重后追加；已存在时返回 False。"""
        if item in result:
            return False
        result.append(item)
        return True

    # 先修缺口固定 1 题，并放在最前面
    for item in gaps[:GAP_QUOTA]:
        add(item)

    # 到期题优先占用复习配额
    due_added = 0
    for item in due:
        if due_added >= due_quota or len(result) >= total:
            break
        if add(item):
            due_added += 1

    # 新卡占用剩余配额
    new_added = 0
    for item in new:
        if new_added >= new_quota or len(result) >= total:
            break
        if add(item):
            new_added += 1

    # 错题变式固定 1 题
    if len(result) < total:
        for item in variants[:VARIANT_QUOTA]:
            add(item)

    # 配额不足时用到期题优先补齐，再补变式/缺口/新卡
    for pool in (due, variants, gaps, new):
        if len(result) >= total:
            break
        for item in pool:
            if len(result) >= total:
                break
            add(item)

    return result[:total]
