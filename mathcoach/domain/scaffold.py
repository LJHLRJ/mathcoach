"""REMSJ 阶段映射：复用现有提示层级，不新增判定或提问。

R/E/M/S/J 只作为提示页的阶段标签，帮助师生对齐当前在练哪一步；
真正的提示内容仍来自 ``hint_ladder`` 与 L3/L4 追问。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScaffoldStage(str, Enum):
    """REMSJ 五个认知阶段。"""

    RESTATE = "restate"
    EXTRACT = "extract"
    MAP = "map"
    SOLVE = "solve"
    JUSTIFY = "justify"


@dataclass(frozen=True)
class StageSpec:
    """一个阶段的展示信息与对应提示层级。"""

    key: ScaffoldStage
    label: str
    description: str
    hint_levels: tuple[int, ...]


STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        ScaffoldStage.RESTATE,
        "复述题意",
        "用自己的话说清题目在问什么",
        (1,),
    ),
    StageSpec(
        ScaffoldStage.EXTRACT,
        "提取条件",
        "找出关键条件、参数或已知量",
        (2,),
    ),
    StageSpec(
        ScaffoldStage.MAP,
        "关联概念",
        "把题目条件对应到知识点或公式",
        (3,),
    ),
    StageSpec(
        ScaffoldStage.SOLVE,
        "求解",
        "按公式或步骤完成计算",
        (4, 5),
    ),
    StageSpec(
        ScaffoldStage.JUSTIFY,
        "说明理由",
        "复述思路并说明为什么这样解",
        (6,),
    ),
)


def stage_for_level(level: int) -> StageSpec:
    """按提示层级返回阶段；未知层级就近回退。"""
    for stage in STAGES:
        if level in stage.hint_levels:
            return stage
    if level <= 0:
        return STAGES[0]
    return STAGES[-1]
