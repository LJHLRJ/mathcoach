"""OpenAI 兼容 Provider：超时 30s、重试 1 次、不流式。"""
import os

from openai import OpenAI

from ..domain.models import Exercise
from .base import ParsedAnswer, RenderTask, UNPARSED
from .prompts import SYSTEM_PARSER, SYSTEM_TUTOR


class OpenAICompatibleProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        client=None,
    ) -> None:
        self.model = model or os.getenv("MODEL", "gpt-4o-mini")
        self._client = client or OpenAI(
            api_key=api_key,
            base_url=base_url or os.getenv("OPENAI_BASE_URL") or None,
            timeout=30.0,      # 单次请求硬超时
            max_retries=1,     # 只重试一次，失败即交给降级层
        )

    def render(self, task: RenderTask) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_TUTOR},
                {"role": "user", "content": task.content},
            ],
        )
        return response.choices[0].message.content.strip()

    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer:
        prompt = (
            "把学生的自由文本作答归一为 JSON，字段：normalized_value（字符串或 null）、"
            f"confidence（0 到 1）、reason（简短理由）。题目：{exercise.stem}"
        )
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PARSER},
                {"role": "user", "content": f"{prompt}\n学生作答：{text}"},
            ],
            response_format={"type": "json_object"},
        )
        try:
            return ParsedAnswer.model_validate_json(response.choices[0].message.content)
        except Exception:
            return UNPARSED  # 任何解析失败都退回未归一，不猜答案
