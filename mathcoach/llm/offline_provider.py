"""离线模板 Provider：确定性文案，不联网。"""
from ..domain.models import Exercise
from .base import ParsedAnswer, RenderTask, UNPARSED


class OfflineProvider:
    """离线模板实现；渲染原样返回素材，解析一律返回 UNPARSED。"""

    def render(self, task: RenderTask) -> str:
        """原样返回素材，离线模式只做确定性文案。"""
        return task.content

    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer:
        """返回 ``UNPARSED``；离线模式不做自由文本归一。"""
        return UNPARSED
