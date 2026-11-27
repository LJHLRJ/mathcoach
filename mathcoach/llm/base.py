"""LLM 层契约：只产出措辞与候选答案，不判分、不改变层级。"""
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from ..domain.models import Exercise


class RenderTask(BaseModel):
    """一次润色任务。

    Attributes:
        kind: 任务类型，``explain`` / ``hint`` / ``feedback``。
        card_name: 知识点名称。
        content: 代码拼好的确定性素材，模型只做措辞润色。
    """

    model_config = ConfigDict(extra="forbid")

    kind: str
    card_name: str
    content: str


class ParsedAnswer(BaseModel):
    """自由文本作答的归一结果；多余字段直接报错。

    Attributes:
        normalized_value: 归一后的答案，无法归一为 None。
        confidence: 置信度 0–1。
        reason: 归一理由，进入引擎前要做注入检测。
    """

    model_config = ConfigDict(extra="forbid")

    normalized_value: str | None
    confidence: float
    reason: str


# 解析失败或离线模式的统一返回值
UNPARSED = ParsedAnswer(normalized_value=None, confidence=0.0, reason="无法归一出答案")


class Provider(Protocol):
    """模型提供方的最小接口。"""

    def render(self, task: RenderTask) -> str:
        """把确定性素材润色成讲解文本。"""
        ...

    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer:
        """把自由文本作答归一成候选答案。"""
        ...
