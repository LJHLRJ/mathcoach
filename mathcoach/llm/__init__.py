"""LLM 层：Provider 装配入口，无 Key 或请求失败时降级为离线模板。"""
import os

from ..domain.models import Exercise
from .base import ParsedAnswer, Provider, RenderTask, UNPARSED
from .offline_provider import OfflineProvider
from .openai_provider import OpenAICompatibleProvider


class FallbackProvider:
    """主 Provider 失败时切到离线模板，并记录降级标记供界面明示。

    Attributes:
        primary: 优先使用的 Provider。
        fallback: 降级用的 Provider。
        degraded: 是否发生过降级。
    """

    def __init__(self, primary: Provider, fallback: Provider) -> None:
        """保存主备 Provider，初始未降级。"""
        self.primary = primary
        self.fallback = fallback
        self.degraded = False

    def render(self, task: RenderTask) -> str:
        """优先走主 Provider；超时、网络或鉴权异常时降级并标记。"""
        try:
            return self.primary.render(task)
        except Exception:
            self.degraded = True
            return self.fallback.render(task)

    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer:
        """优先走主 Provider；异常时降级并标记。"""
        try:
            return self.primary.parse_freeform(text, exercise)
        except Exception:
            self.degraded = True
            return self.fallback.parse_freeform(text, exercise)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """优先走主 Provider；失败时标记降级并抛出。

        追问引擎捕获异常后回退到原 L3–L4 陈述式提示，不阻断做题。
        """
        try:
            return self.primary.complete(system_prompt, user_prompt)
        except Exception:
            self.degraded = True
            raise


def build_provider() -> Provider:
    """按环境变量装配 Provider。

    有 ``OPENAI_API_KEY`` 时用 OpenAI 兼容实现并套降级；没有则纯离线。

    Returns:
        可直接调用的 ``Provider``。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return OfflineProvider()
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
