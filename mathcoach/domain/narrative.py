"""叙事线纯函数：按顺序点亮节点，不允许跳级。"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class NarrativeNode:
    """叙事线节点。

    Attributes:
        id: 节点 ID。
        card_id: 解锁该节点要完成的知识点卡。
        name: 节点名称。
        description: 节点说明，显示在仪表盘。
    """

    id: str
    card_id: str
    name: str
    description: str


@dataclass(frozen=True)
class NarrativeProgress:
    """叙事线进度。

    Attributes:
        unlocked: 已点亮节点 ID，按点亮顺序排列。
    """

    unlocked: tuple[str, ...] = ()


def first_node(nodes: list[NarrativeNode]) -> NarrativeNode | None:
    """返回第一个节点；列表为空时返回 None。"""
    return nodes[0] if nodes else None


def initial_progress(nodes: list[NarrativeNode]) -> NarrativeProgress:
    """初始进度只点亮第一个节点；列表为空时为空进度。"""
    return NarrativeProgress((nodes[0].id,)) if nodes else NarrativeProgress(())


def advance(
    progress: NarrativeProgress,
    nodes: list[NarrativeNode],
    card_id: str,
    enabled: bool = True,
) -> NarrativeProgress:
    """完成下一个节点对应的卡后推进一格。

    只在 ``enabled``、进度非空、且 ``card_id`` 正好是下一个节点的卡时生效，
    跳级或完成其他卡都原样返回。

    Args:
        progress: 当前进度。
        nodes: 叙事线节点，按顺序排列。
        card_id: 本次完成的卡 ID。
        enabled: 叙事线开关。

    Returns:
        新的进度；未推进时返回原对象。
    """
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
    """从已完成卡片集合重放进度。

    从初始进度开始按节点顺序逐个调用 ``advance``，中间缺卡就停下，
    所以跳级无法生效。

    Args:
        nodes: 叙事线节点，按顺序排列。
        completed_card_ids: 已完成的知识点卡。

    Returns:
        重放后的进度。
    """
    progress = initial_progress(nodes)
    for node in nodes[1:]:
        if node.card_id in completed_card_ids:
            progress = advance(progress, nodes, node.card_id)
    return progress


def next_node(
    progress: NarrativeProgress, nodes: list[NarrativeNode]
) -> NarrativeNode | None:
    """返回下一个未点亮节点；已走完或列表为空时返回 None。"""
    if not nodes:
        return None
    index = len(progress.unlocked)
    return nodes[index] if index < len(nodes) else None


def narrative_closed(
    progress: NarrativeProgress, nodes: list[NarrativeNode]
) -> bool:
    """所有节点都已点亮时返回 True；空列表视为未完成。"""
    return bool(nodes) and len(progress.unlocked) >= len(nodes)
