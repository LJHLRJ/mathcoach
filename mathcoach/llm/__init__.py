"""LLM 层：Provider 装配入口，无 Key 或请求失败时降级为离线模板。"""
import os

from .base import ParsedAnswer, Provider, RenderTask, UNPARSED
from .offline_provider import OfflineProvider
from .openai_provider import OpenAICompatibleProvider


class FallbackProvider:
    """主 Provider 失败时切换到离线模板，并记录降级标记供界面明示。"""

    def __init__(self, primary, fallback) -> None:
        self.primary = primary
        self.fallback = fallback
        self.degraded = False

    def render(self, task: RenderTask) -> str:
        try:
            return self.primary.render(task)
        except Exception:
            self.degraded = True  # 超时/网络错误/鉴权失败统一降级
            return self.fallback.render(task)

    def parse_freeform(self, text: str, exercise) -> ParsedAnswer:
        try:
            return self.primary.parse_freeform(text, exercise)
        except Exception:
            self.degraded = True
            return self.fallback.parse_freeform(text, exercise)


def build_provider() -> Provider:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return OfflineProvider()  # 未配置 Key：纯离线，不发请求
    return FallbackProvider(
        primary=OpenAICompatibleProvider(api_key=api_key),
        fallback=OfflineProvider(),
    )


__all__ = [
    "FallbackProvider",
    "OfflineProvider",
    "OpenAICompatibleProvider",
    "ParsedAnswer",
    "Provider",
    "RenderTask",
    "UNPARSED",
    "build_provider",
]
