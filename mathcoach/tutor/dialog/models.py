"""追问引擎数据结构：追问元数据、三档判定与效果信号。

追问的数学内容由元数据给出并经 verify 预检；LLM 只改写问法。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class DialogOutcome(str, Enum):
    """学生回答的三档判定。"""

    HIT = "hit"
    PARTIAL = "partial"
    MISS = "miss"


class DialogEventKind(str, Enum):
    """写入效果信号的事件类型。"""

    HIT = "hit"
    PARTIAL = "partial"
    MISS = "miss"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FALLBACK = "fallback"


class FollowUpSpec(BaseModel):
    """一道题在某一级的追问元数据。

    ``expression`` / ``expected`` 交给 verify 复核；``acceptable`` 是
    2–4 条可接受回答要点，供轻量判定使用。``template_prompt`` 只作
    确定性的问法与 LLM 输入，不直接作为最终展示文案。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    exercise_id: str
    level: int
    kc_ids: tuple[str, ...]
    expression: str
    expected: str
    variables: tuple[str, ...] = ()
    facts: dict[str, str] = Field(default_factory=dict)
    acceptable: tuple[str, ...]
    template_prompt: str
    supplement_prompt: str
    forbidden_in_prompt: tuple[str, ...] = ()


class FollowUpWording(BaseModel):
    """LLM 只返回追问问法。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str


@dataclass(frozen=True)
class FollowUp:
    """一条可展示的追问。"""

    spec: FollowUpSpec
    prompt: str
    supplement: bool = False


@dataclass(frozen=True)
class FollowUpBuild:
    """追问构建结果；失败时带降级原因。"""

    follow_up: FollowUp | None
    spec: FollowUpSpec | None = None
    fallback_reason: str = ""
    verify_verdict: str = ""


@dataclass(frozen=True)
class DialogEvent:
    """一次追问事件，用于效果信号。

    ``answer`` 必须已脱敏；``downgraded`` 表示本次是否直接降到 L5。
    """

    exercise_id: str
    card_id: str
    kc_ids: tuple[str, ...]
    level: int
    supplement: bool
    kind: DialogEventKind
    downgraded: bool
    shown_at: datetime
    resolved_at: datetime
    answer: str = ""
    reason: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
