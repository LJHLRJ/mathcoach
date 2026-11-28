"""语音输入：本地转写 + 数学口语规范化，失败回退文字输入。"""
from .local_whisper import LocalWhisperTranscriber, voice_available
from .models import Transcriber, Transcription
from .normalize import normalize_spoken_math
from .service import transcribe_and_normalize

__all__ = [
    "LocalWhisperTranscriber",
    "Transcriber",
    "Transcription",
    "normalize_spoken_math",
    "transcribe_and_normalize",
    "voice_available",
]
