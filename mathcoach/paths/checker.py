"""路径检查点判定：复用步骤判定，不新增数学引擎。"""
from __future__ import annotations

from collections.abc import Callable

from ..steps.checker import check_step
from ..steps.models import StepSpec, StepVerdict
from ..verify.symbolic import SymbolicVerdict
from .models import PathCheckpoint

PathVerifyFn = Callable[[str, str, frozenset[str]], SymbolicVerdict]


def check_checkpoint(
    checkpoint: PathCheckpoint,
    answer: str,
    *,
    verify_fn: PathVerifyFn | None = None,
) -> StepVerdict:
    """判定一个路径检查点；空输入按错误处理。

    Args:
        checkpoint: 路径检查点元数据。
        answer: 学生输入。
        verify_fn: 表达式验证函数；None 使用步骤判定的离线 verify。

    Returns:
        ``StepVerdict``；不会因检查点判定失败而抛出异常。
    """
    spec = StepSpec(
        exercise_id="",
        index=checkpoint.index,
        prompt=checkpoint.prompt,
        expected=checkpoint.expected,
        variables=checkpoint.variables,
        input_kind=checkpoint.input_kind,
        acceptable=checkpoint.acceptable,
    )
    return check_step(spec, answer, verify_fn=verify_fn)
