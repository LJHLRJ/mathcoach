"""表示降级事件模型：只记录教学形态选择，不写正式学习档案。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from ..domain.representation import Representation


@dataclass(frozen=True)
class RepresentationEvent:
    """一次表示降级事件。

    ``resolved_at`` / ``next_correct`` / ``next_hint_level`` 在降级后的
    下一次作答时回填；未观测到结果时保持 ``None``。
    """

    exercise_id: str
    card_id: str
    from_repr: Representation
    to_repr: Representation
    triggers: tuple[str, ...] = ()
    kc_id: str = ""
    shown_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    id: str = field(default_factory=lambda: uuid4().hex)
    resolved_at: datetime | None = None
    next_correct: bool | None = None
    next_hint_level: int | None = None


class RepresentationRecorder(Protocol):
    """表示事件记录接口；会话引擎只依赖该协议。"""

    def record(self, event: RepresentationEvent) -> str:
        """写入一条降级事件，返回事件 ID。"""
        ...

    def record_outcome(
        self, event_id: str, *, correct: bool | None, hint_level: int
    ) -> None:
        """回填降级后的第一次作答结果。"""
        ...
