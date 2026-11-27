"""会话视图：engine 产出，app 只做渲染。"""
from dataclasses import dataclass

from ..domain.models import Phase, Receipt


@dataclass(frozen=True)
class SessionView:
    """一帧会话视图，app 按字段直接渲染。

    Attributes:
        phase: 当前阶段。
        title: 标题。
        body: 正文。
        options: 可选按钮或选项。
        notice: 辅助提示，可为空。
        receipt: 刚生成的收据。
        receipts: 本次会话已生成的收据。
    """

    phase: Phase
    title: str
    body: str
    options: tuple[str, ...] = ()
    notice: str = ""
    receipt: Receipt | None = None
    receipts: tuple[Receipt, ...] = ()
