"""学习路径纯函数：先修拓扑排序 + 未掌握卡片推荐。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Recommendation:
    card_id: str
    reason: str
    basis: str


def topological_order(
    card_ids: list[str], prerequisites: dict[str, list[str]]
) -> list[str]:
    """Kahn 拓扑排序；先修图有环时抛 ValueError。"""
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
) -> list[Recommendation]:
    """只推荐未掌握卡片；先修已满足的错题卡优先。"""
    order = topological_order(card_ids, prerequisites)
    weak = weak_cards or set()
    unmastered = [card_id for card_id in order if card_id not in mastered]
    ready = [
        card_id
        for card_id in unmastered
        if all(parent in mastered for parent in prerequisites.get(card_id, []))
    ]
    weak_ready = [card_id for card_id in ready if card_id in weak]
    other_ready = [card_id for card_id in ready if card_id not in weak]
    chosen = (weak_ready + other_ready)[:limit]
    if len(chosen) < limit:
        # 先修尚未满足时仍按拓扑顺序给出后续候选，避免推荐为空
        for card_id in unmastered:
            if card_id not in chosen:
                chosen.append(card_id)
            if len(chosen) >= limit:
                break

    recommendations: list[Recommendation] = []
    for card_id in chosen:
        parents = prerequisites.get(card_id, [])
        if card_id in weak:
            reason = "近期错题较多，优先巩固"
            basis = f"先修 {len(parents)} 张；错题优先"
        else:
            reason = "先修已满足，按拓扑顺序推进"
            basis = f"先修 {len(parents)} 张均已满足"
        recommendations.append(Recommendation(card_id, reason, basis))
    return recommendations
