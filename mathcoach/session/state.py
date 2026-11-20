"""会话视图：engine 产出，app 只负责渲染。"""
from dataclasses import dataclass

from ..domain.models import Phase, Receipt


@dataclass(frozen=True)
class SessionView:
    phase: Phase
    title: str
    body: str
    options: tuple[str, ...] = ()
    notice: str = ""
    receipt: Receipt | None = None
    receipts: tuple[Receipt, ...] = ()
