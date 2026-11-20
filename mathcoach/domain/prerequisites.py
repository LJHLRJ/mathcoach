"""先修链诊断：沿先修边 BFS 向上追溯，识别概念缺口。"""
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class MistakeStat:
    total: int
    concept_wrong: int


@dataclass(frozen=True)
class Gap:
    chain: tuple[str, ...]
    reason: str


def _is_gap(stat: MistakeStat) -> bool:
    """错题达到 2 次且概念错占比过半，才判定为先修缺口。"""
    return stat.total >= 2 and stat.concept_wrong / stat.total >= 0.5


def trace_gap(
    card_id: str,
    prerequisites: dict[str, list[str]],
    stats: dict[str, MistakeStat],
    max_depth: int = 2,
) -> list[Gap]:
    gaps: list[Gap] = []
    # 队列元素：(当前节点, 从起点到当前节点的链, 已走深度)
    queue = deque([(card_id, (card_id,), 0)])
    while queue:
        node, chain, depth = queue.popleft()
        if depth >= max_depth:
            continue  # 到深度上限就不再向上展开
        for parent in prerequisites.get(node, []):
            new_chain = chain + (parent,)
            stat = stats.get(parent)
            if stat and _is_gap(stat):
                gaps.append(
                    Gap(
                        chain=new_chain,
                        reason=f"前置知识点概念错 {stat.concept_wrong}/{stat.total} 次",
                    )
                )
            queue.append((parent, new_chain, depth + 1))
    return gaps
