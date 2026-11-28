"""语音服务：转写 + 数学口语规范化；失败时返回 None 供 UI 回退。"""
from __future__ import annotations

from .local_whisper import LocalWhisperTranscriber
from .models import Transcriber, Transcription
from .normalize import normalize_spoken_math


def transcribe_and_normalize(
    audio: bytes,
    *,
    transcriber: Transcriber | None = None,
) -> str | None:
    """转写并规范化一段语音；没有可用文本时返回 None。

    Args:
        audio: 录音字节。
        transcriber: 可注入的转写器；缺省使用本地 Whisper。

    Returns:
        规范化后的文本；空音频、缺依赖、识别为空或失败时返回 None。
    """
    if not audio:
        return None
    active = transcriber or LocalWhisperTranscriber()
    result = active.transcribe(audio)
    if result is None or not result.text.strip():
        return None
    normalized = normalize_spoken_math(result.text)
    return normalized or None


__all__ = [
    "LocalWhisperTranscriber",
    "Transcriber",
    "Transcription",
    "normalize_spoken_math",
    "transcribe_and_normalize",
]
