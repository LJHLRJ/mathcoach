"""会话视图：engine 产出，app 只做渲染。"""
from dataclasses import dataclass

from ..domain.models import Phase, Receipt
from ..domain.representation import Representation


@dataclass(frozen=True)
class FollowUpView:
    """一帧追问视图。

    Attributes:
        level: 追问所在层级，当前为 L3 或 L4。
        prompt: 已通过校验的追问问法。
        supplement: 是否是部分命中后的补充追问。
        anchor_step_index: 追问锚定的步骤序号；None 表示整题级追问。
    """

    level: int
    prompt: str
    supplement: bool = False
    anchor_step_index: int | None = None


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
        follow_up: L3–L4 追问；None 表示普通陈述式提示。
        representation: 表示降级后的讲解形态；None 表示沿用默认形态。
    """

    phase: Phase
    title: str
    body: str
    options: tuple[str, ...] = ()
    notice: str = ""
    receipt: Receipt | None = None
    receipts: tuple[Receipt, ...] = ()
    follow_up: FollowUpView | None = None
    representation: Representation | None = None
