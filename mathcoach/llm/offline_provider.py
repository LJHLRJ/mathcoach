"""离线模板 Provider：确定性文案，不联网。"""
from ..domain.models import Exercise
from .base import ParsedAnswer, RenderTask, UNPARSED


class OfflineProvider:
    def render(self, task: RenderTask) -> str:
        return task.content  # 素材由代码拼装，模板模式原样返回

    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer:
        return UNPARSED  # 离线模式不做自由文本归一，界面引导改用选项
