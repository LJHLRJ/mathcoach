"""语音转写数据结构与可插拔接口；音频默认不落盘、不出本机。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Transcription:
    """一次语音转写结果。

    Attributes:
        text: 原始转写文本，尚未做数学规范化。
        provider: 转写来源，如 ``local-whisper``。
        confidence: 平均置信度；不可得时为 None。
    """

    text: str
    provider: str = "local-whisper"
    confidence: float | None = None


class Transcriber(Protocol):
    """语音转写接口；失败返回 None，由上层回退文字输入。"""

    def transcribe(
        self, audio: bytes, *, suffix: str = ".wav"
    ) -> Transcription | None:
        """把音频字节转成文本；不可用或失败时返回 None。"""
        ...
