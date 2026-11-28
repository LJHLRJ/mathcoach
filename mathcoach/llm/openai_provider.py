"""OpenAI 兼容 Provider：超时 30s、重试 1 次、不流式。"""
import os
from typing import Any

from openai import OpenAI

from ..domain.models import Exercise
from .base import ParsedAnswer, RenderTask, UNPARSED
from .prompts import SYSTEM_PARSER, SYSTEM_TUTOR


class OpenAICompatibleProvider:
    """OpenAI 兼容接口实现；不流式。"""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        client: Any = None,
    ) -> None:
        """创建 Provider。

        Args:
            api_key: 接口密钥。
            base_url: 兼容接口地址，缺省读 ``OPENAI_BASE_URL``。
            model: 模型名，缺省读 ``MODEL``，最后回落到 ``gpt-4o-mini``。
            client: 测试注入的客户端，传入后不再自建。
        """
        self.model = model or os.getenv("MODEL", "gpt-4o-mini")
        self._client = client or OpenAI(
            api_key=api_key,
            base_url=base_url or os.getenv("OPENAI_BASE_URL") or None,
            timeout=30.0,      # 单次请求硬超时
            max_retries=1,     # 只重试一次，失败即交给降级层
        )

    def render(self, task: RenderTask) -> str:
        """用教学提示词润色讲解文本，返回去掉首尾空白的回复。"""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_TUTOR},
                {"role": "user", "content": task.content},
            ],
        )
        return response.choices[0].message.content.strip()

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """通用 JSON 补全；供追问引擎等结构化任务使用。"""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content.strip()

    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer:
        """把自由文本作答归一为 JSON。

        Args:
            text: 学生作答原文。
            exercise: 当前题目，题干会拼进提示词。

        Returns:
            校验通过的 ``ParsedAnswer``；校验失败返回 ``UNPARSED``，不猜答案。
        """
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
