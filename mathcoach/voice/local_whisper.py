"""本地 Whisper 转写：可选依赖，音频只在本机处理。

``faster-whisper`` 不在运行时依赖中；未安装时 ``voice_available`` 返回
False，UI 隐藏语音入口并保留文字输入。首次转写会加载/下载模型。
"""
from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path

from .models import Transcription

DEFAULT_MODEL = os.getenv("MATHCOACH_WHISPER_MODEL", "small")
_MODEL_CACHE: dict[str, object] = {}


def voice_available() -> bool:
    """本地转写依赖是否可用。"""
    return importlib.util.find_spec("faster_whisper") is not None


class LocalWhisperTranscriber:
    """基于 faster-whisper 的本地转写器；任何失败都返回 None。"""

    def __init__(self, model_size: str | None = None) -> None:
        self.model_size = model_size or DEFAULT_MODEL

    def _model(self) -> object | None:
        """按模型大小缓存实例，避免每次录音重复加载。"""
        cached = _MODEL_CACHE.get(self.model_size)
        if cached is not None:
            return cached
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return None
        try:
            model = WhisperModel(
                self.model_size, device="cpu", compute_type="int8"
            )
        except Exception:
            return None
        _MODEL_CACHE[self.model_size] = model
        return model

    def transcribe(
        self, audio: bytes, *, suffix: str = ".wav"
    ) -> Transcription | None:
        """转写音频；空音频、缺依赖或识别失败返回 None。"""
        if not audio or not voice_available():
            return None
        model = self._model()
        if model is None:
            return None
        path = ""
        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            ) as handle:
                handle.write(audio)
                path = handle.name
            segments, _ = model.transcribe(
                path, language="zh", vad_filter=True
            )
            text = "".join(segment.text for segment in segments).strip()
        except Exception:
            return None
        finally:
            if path:
                Path(path).unlink(missing_ok=True)
        if not text:
            return None
        return Transcription(text=text, provider="local-whisper")
