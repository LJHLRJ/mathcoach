"""分步板书帧：帧元数据与按题/步骤查询；只读，不参与判定。"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BoardFrameSpec:
    """一道题在某一步的板书帧。

    Attributes:
        exercise_id: 所属题目。
        step_index: 对应 ``StepSpec.index``。
        title: 帧标题。
        narration: 该帧的文字说明。
        figure: 图形名，对应板书渲染器的注册键。
        params: 图形参数，如振幅、角频率、边长。
        highlight: 需要强调的图形元素。
        kc_id: 关联知识点。
        dialog_level: 该帧可锚定的追问层级（L3/L4）。
        verify_expression: 帧内数学声明的表达式。
        verify_expected: 期望结果，供 verify 预检。
        verify_variables: 表达式允许的变量。
    """

    exercise_id: str
    step_index: int
    title: str
    narration: str
    figure: str
    params: Mapping[str, float] = field(default_factory=dict)
    highlight: str = ""
    kc_id: str = ""
    dialog_level: int | None = None
    verify_expression: str = ""
    verify_expected: str = ""
    verify_variables: tuple[str, ...] = ()


@dataclass(frozen=True)
class BoardCatalog:
    """板书帧目录；``errors`` 保存被跳过的帧或文件错误。"""

    frames: Mapping[str, tuple[BoardFrameSpec, ...]]
    errors: tuple[str, ...] = ()


def frames_for(
    catalog: BoardCatalog, exercise_id: str
) -> tuple[BoardFrameSpec, ...]:
    """返回一道题的全部帧；未知题目返回空元组。"""
    return catalog.frames.get(exercise_id, ())


def frame_for(
    catalog: BoardCatalog, exercise_id: str, step_index: int
) -> BoardFrameSpec | None:
    """按题与步骤返回一帧；缺失返回 None。"""
    for frame in frames_for(catalog, exercise_id):
        if frame.step_index == step_index:
            return frame
    return None
