"""LLM 层契约：只产出措辞与候选答案，不判分、不改变层级。"""
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from ..domain.models import Exercise


class RenderTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str          # explain / hint / feedback
    card_name: str
    content: str       # 由代码拼好的确定性素材，模型只做措辞润色


class ParsedAnswer(BaseModel):
    """严格模型：不接收任意 dict，多余字段直接报错。"""

    model_config = ConfigDict(extra="forbid")

    normalized_value: str | None
    confidence: float   # 0.0 - 1.0
    reason: str         # 进入引擎前必须做注入检测（M5）


UNPARSED = ParsedAnswer(normalized_value=None, confidence=0.0, reason="无法归一出答案")


class Provider(Protocol):
    def render(self, task: RenderTask) -> str: ...

    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer: ...
