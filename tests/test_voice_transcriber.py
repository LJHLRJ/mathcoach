"""语音服务：转写失败、缺依赖与空结果都回退为 None。"""
import importlib.util

from mathcoach.voice import (
    LocalWhisperTranscriber,
    Transcription,
    transcribe_and_normalize,
    voice_available,
)


class FakeTranscriber:
    """按固定文本返回转写结果。"""

    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, audio: bytes, *, suffix: str = ".wav"):
        if not audio:
            return None
        return Transcription(text=self.text)


class EmptyTranscriber:
    """模拟识别为空。"""

    def transcribe(self, audio: bytes, *, suffix: str = ".wav"):
        return Transcription(text="  ")


def test_transcribe_and_normalize_returns_math_text():
    """转写结果会经过口语规范化。"""
    result = transcribe_and_normalize(
        b"audio", transcriber=FakeTranscriber("十六分之二十五")
    )
    assert result == "25/16"


def test_empty_audio_returns_none():
    """空音频不调用转写。"""
    assert transcribe_and_normalize(b"") is None


def test_empty_transcription_returns_none():
    """识别为空时返回 None，供 UI 提示改用文字。"""
    assert (
        transcribe_and_normalize(b"audio", transcriber=EmptyTranscriber())
        is None
    )


def test_voice_available_detects_missing_dependency(monkeypatch):
    """缺少 faster-whisper 时语音入口应隐藏。"""
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert not voice_available()


def test_local_transcriber_returns_none_without_dependency(monkeypatch):
    """缺依赖时本地转写直接返回 None，不抛异常。"""
    monkeypatch.setattr(
        "mathcoach.voice.local_whisper.voice_available", lambda: False
    )
    assert LocalWhisperTranscriber().transcribe(b"audio") is None
