"""多解路径的数据结构；只描述内容，不参与判分或掌握度更新。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PathCheckpoint:
    """一条路径上的一个可验证检查点。

    ``verify_expected`` 只在表达式检查点上使用：它与 ``expected`` 必须
    等价，用于加载期证明该检查点没有写错。
    """

    index: int
    prompt: str
    expected: str
    variables: tuple[str, ...] = ()
    input_kind: str = "expr"
    acceptable: tuple[str, ...] = ()
    verify_expected: str = ""


@dataclass(frozen=True)
class SolutionPath:
    """一道题的一条备选解法。"""

    exercise_id: str
    path_id: str
    name: str
    summary: str
    checkpoints: tuple[PathCheckpoint, ...]
    final_answer: str = ""
    kc_ids: tuple[str, ...] = ()
    verify_expression: str = ""
    verify_expected: str = ""
    variables: tuple[str, ...] = ()
