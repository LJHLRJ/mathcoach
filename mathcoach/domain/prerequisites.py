"""先修链诊断：沿先修边 BFS 向上追溯，识别概念缺口。"""
from collections import deque
from dataclasses import dataclass

from .basis import basis_for_gap


@dataclass(frozen=True)
class MistakeStat:
    """某个知识点的错题统计。

    Attributes:
        total: 错题总数。
        concept_wrong: 其中概念性错误的数量。
    """

    total: int
    concept_wrong: int


@dataclass(frozen=True)
class Gap:
    """一条先修缺口。

    Attributes:
        chain: 从起点卡到缺口先修节点的链，首元素是起点。
        reason: 缺口说明，含概念错次数。
        basis: 生成时写入的依据，供视图直接展示。
    """

    chain: tuple[str, ...]
    reason: str
    basis: str = ""


def _is_gap(stat: MistakeStat) -> bool:
    """错题达到 2 次且概念错占比过半，才判定为先修缺口。"""
    return stat.total >= 2 and stat.concept_wrong / stat.total >= 0.5


def trace_gap(
    card_id: str,
    prerequisites: dict[str, list[str]],
    stats: dict[str, MistakeStat],
    max_depth: int = 2,
) -> list[Gap]:
    """沿先修边向上找概念缺口。

    从 ``card_id`` 开始 BFS，逐层展开先修节点，深度到 ``max_depth`` 停止。
    错题达到阈值（见 ``_is_gap``）的先修节点记一条 ``Gap``，``chain`` 保留完整路径。

    Note:
        每个节点只展开一次，菱形先修或共享祖先不会重复报同一个缺口；
        先修有环时也不会一直展开。

    Args:
        card_id: 起点卡 ID。
        prerequisites: 子节点 -> 先修节点列表。
        stats: 知识点错题统计，缺失的节点按无错题处理。
        max_depth: 向上追溯的层数，0 表示不展开。

    Returns:
        缺口列表，顺序由 BFS 决定。
    """
    gaps: list[Gap] = []
    visited = {card_id}
    # 队列元素：(当前节点, 从起点到当前节点的链, 已走深度)
    queue = deque([(card_id, (card_id,), 0)])
    while queue:
        node, chain, depth = queue.popleft()
        if depth >= max_depth:
            continue  # 到深度上限就不再向上展开
        for parent in prerequisites.get(node, []):
            if parent in visited:
                continue
            visited.add(parent)
            new_chain = chain + (parent,)
            stat = stats.get(parent)
            if stat and _is_gap(stat):
                gaps.append(
                    Gap(
                        chain=new_chain,
                        reason=f"前置知识点概念错 {stat.concept_wrong}/{stat.total} 次",
                        basis=basis_for_gap(stat),
                    )
                )
            queue.append((parent, new_chain, depth + 1))
    return gaps
