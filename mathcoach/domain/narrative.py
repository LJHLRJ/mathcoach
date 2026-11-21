"""叙事线纯函数：按顺序点亮节点，不允许跳级。"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class NarrativeNode:
    id: str
    card_id: str
    name: str
    description: str


@dataclass(frozen=True)
class NarrativeProgress:
    unlocked: tuple[str, ...] = ()


def first_node(nodes: list[NarrativeNode]) -> NarrativeNode | None:
    return nodes[0] if nodes else None


def initial_progress(nodes: list[NarrativeNode]) -> NarrativeProgress:
    return NarrativeProgress((nodes[0].id,)) if nodes else NarrativeProgress(())


def advance(
    progress: NarrativeProgress,
    nodes: list[NarrativeNode],
    card_id: str,
    enabled: bool = True,
) -> NarrativeProgress:
    """只有完成“下一个节点”的卡片才推进；跳级请求保持原状。"""
    if not enabled or not nodes or not progress.unlocked:
        return progress
    current_index = next(
        (
            index
            for index, node in enumerate(nodes)
            if node.id == progress.unlocked[-1]
        ),
        None,
    )
    if current_index is None or current_index + 1 >= len(nodes):
        return progress
    next_node = nodes[current_index + 1]
    if next_node.card_id != card_id:
        return progress
    return replace(progress, unlocked=progress.unlocked + (next_node.id,))


def build_progress(
    nodes: list[NarrativeNode], completed_card_ids: set[str]
) -> NarrativeProgress:
    """按节点顺序消费已完成卡片，天然阻止跳级。"""
    progress = initial_progress(nodes)
    for node in nodes[1:]:
        if node.card_id in completed_card_ids:
            progress = advance(progress, nodes, node.card_id)
    return progress


def next_node(
    progress: NarrativeProgress, nodes: list[NarrativeNode]
) -> NarrativeNode | None:
    if not nodes:
        return None
    index = len(progress.unlocked)
    return nodes[index] if index < len(nodes) else None


def narrative_closed(
    progress: NarrativeProgress, nodes: list[NarrativeNode]
) -> bool:
    return bool(nodes) and len(progress.unlocked) >= len(nodes)
