"""学习路径纯函数：先修拓扑排序 + 未掌握卡片推荐。"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

from .bkt import initial_mastery


@dataclass(frozen=True)
class Recommendation:
    """一条学习路径推荐。

    Attributes:
        card_id: 推荐的知识点卡 ID。
        reason: 推荐理由。
        basis: 依据摘要，供视图直接展示。
    """

    card_id: str
    reason: str
    basis: str


def topological_order(
    card_ids: list[str], prerequisites: dict[str, list[str]]
) -> list[str]:
    """按先修关系排出学习顺序。

    Kahn 算法：入度为 0 的节点按 ID 升序入队，出队后减少子节点入度。
    只考虑 ``card_ids`` 里的节点，指向集合外的先修边忽略。

    Args:
        card_ids: 待排序的卡 ID，重复项只保留第一次出现。
        prerequisites: 子节点 -> 先修节点列表。

    Returns:
        拓扑序卡 ID 列表。

    Raises:
        ValueError: 先修图存在环，排不出完整顺序。
    """
    nodes = list(dict.fromkeys(card_ids))
    node_set = set(nodes)
    indegree = {node: 0 for node in nodes}
    children: dict[str, list[str]] = {node: [] for node in nodes}
    for child, parents in prerequisites.items():
        if child not in node_set:
            continue
        for parent in parents:
            if parent in node_set:
                indegree[child] += 1
                children[parent].append(child)

    ready = deque(sorted(node for node in nodes if indegree[node] == 0))
    order: list[str] = []
    while ready:
        node = ready.popleft()
        order.append(node)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if len(order) != len(nodes):
        raise ValueError("先修图存在环")
    return order


def recommend(
    card_ids: list[str],
    prerequisites: dict[str, list[str]],
    mastered: set[str],
    weak_cards: set[str] | None = None,
    limit: int = 3,
    mastery: Mapping[str, float] | None = None,
) -> list[Recommendation]:
    """挑出接下来要学的卡。

    先按拓扑序滤掉已掌握的卡，先修全部满足的算就绪；就绪卡里错题卡排前面，
    其余按 BKT 掌握度从低到高排列，再补到 ``limit`` 条。没有掌握度记录的卡
    按初始掌握概率参与排序。

    Note:
        就绪卡不足 ``limit`` 时按拓扑序补未就绪的卡，这些卡会在 ``reason`` /
        ``basis`` 里标明先修尚未满足。

    Args:
        card_ids: 全部卡 ID。
        prerequisites: 子节点 -> 先修节点列表。
        mastered: 已掌握的卡 ID。
        weak_cards: 近期错题较多的卡 ID，优先推荐。
        limit: 最多返回几条。
        mastery: 卡 ID -> BKT 掌握概率，用来在同类候选中从低到高排序。

    Returns:
        推荐列表，最多 ``limit`` 条。

    Raises:
        ValueError: 先修图存在环。
    """
    order = topological_order(card_ids, prerequisites)
    weak = weak_cards or set()
    probabilities = mastery or {}
    position = {
        card_id: index for index, card_id in enumerate(order)
    }

    def priority(card_id: str) -> tuple[float, int]:
        """按掌握度升序、拓扑位置升序排序候选项。"""
        return (
            probabilities.get(card_id, initial_mastery()),
            position[card_id],
        )

    unmastered = [card_id for card_id in order if card_id not in mastered]
    ready = [
        card_id
        for card_id in unmastered
        if all(parent in mastered for parent in prerequisites.get(card_id, []))
    ]
    weak_ready = sorted(
        (card_id for card_id in ready if card_id in weak), key=priority
    )
    other_ready = sorted(
        (card_id for card_id in ready if card_id not in weak), key=priority
    )
    chosen = (weak_ready + other_ready)[:limit]
    if len(chosen) < limit:
        # 先修尚未满足时仍按拓扑顺序给出后续候选，避免推荐为空
        for card_id in unmastered:
            if card_id not in chosen:
                chosen.append(card_id)
            if len(chosen) >= limit:
                break

    ready_set = set(ready)
    recommendations: list[Recommendation] = []
    for card_id in chosen:
        parents = prerequisites.get(card_id, [])
        unmet = [parent for parent in parents if parent not in mastered]
        bkt_text = (
            f"BKT 掌握度 {probabilities[card_id]:.0%}"
            if card_id in probabilities
            else "BKT 暂无记录"
        )
        if card_id not in ready_set:
            reason = "先修尚未满足，按拓扑顺序提前预习"
            basis = f"先修 {len(parents)} 张，待掌握 {len(unmet)} 张"
            if probabilities:
                basis += f"；{bkt_text}"
        elif card_id in weak:
            reason = "近期错题较多，优先巩固"
            basis = f"先修 {len(parents)} 张；错题优先"
            if probabilities:
                basis += f"；{bkt_text}"
        elif probabilities:
            reason = "先修已满足，按掌握度优先补强"
            basis = f"先修 {len(parents)} 张均已满足；{bkt_text}"
        else:
            reason = "先修已满足，按拓扑顺序推进"
            basis = f"先修 {len(parents)} 张均已满足"
        recommendations.append(Recommendation(card_id, reason, basis))
    return recommendations
