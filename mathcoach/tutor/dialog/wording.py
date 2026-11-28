"""追问问法生成：LLM 只改写措辞，数学内容来自追问元数据。

确定性校验：
- 问法不得出现元数据之外的新数字/表达式；
- 不得包含最终答案或元数据声明的泄露词；
- 任何模型/解析失败都交给上层回退到原 L3–L4 陈述式提示。
"""
from __future__ import annotations

import json
import re
import unicodedata
from fractions import Fraction
from typing import Protocol, cast

from .models import FollowUpSpec, FollowUpWording

PROMPT_VERSION = "dialog-follow-up-1"
MAX_PROMPT_CHARS = 160
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")

SYSTEM_FOLLOW_UP = (
    f"prompt_version={PROMPT_VERSION} 你只改写数学追问的问法。"
    "追问涉及的数学内容（数字、表达式、中间结果、答案）已由确定性代码给出，"
    "你不得新增、删除或修改任何数学内容；不得在追问中给出最终答案。"
    "只输出 JSON，字段为 prompt。"
)


class FollowUpClient(Protocol):
    """追问问法生成所需的最小模型客户端。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """返回模型原始文本，期望为 JSON。"""
        ...


def build_follow_up_client(provider: object) -> FollowUpClient | None:
    """从教学 Provider 提取带 ``complete`` 的追问客户端。

    离线 Provider 没有 ``complete`` 时返回 None，追问引擎随之外退到
    原 L3–L4 陈述式提示。
    """
    complete = getattr(provider, "complete", None)
    if callable(complete):
        return cast(FollowUpClient, provider)
    return None


def _normalize(text: str) -> str:
    """统一全角、大小写与负号，便于数字和泄露词比较。"""
    return unicodedata.normalize("NFKC", text).lower().replace("−", "-")


def _number_texts(text: str) -> list[str]:
    """提取文本中的数字/分数 token。"""
    return _NUMBER.findall(_normalize(text))


def _numeric_value(text: str) -> Fraction | None:
    """把数字/分数 token 转成有理数；无法解析时为 None。"""
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def _allowed_numbers(spec: FollowUpSpec) -> set[str]:
    """允许出现在问法里的数字 token。

    分数会额外展开分子/分母，避免 LLM 改写时把 ``3/5`` 拆成
    ``3`` 与 ``5`` 被误判为新增数字。
    """
    source = " ".join(
        [
            spec.expression,
            spec.expected,
            spec.template_prompt,
            spec.supplement_prompt,
            *spec.facts.values(),
        ]
    )
    numbers = set(_number_texts(source))
    allowed = set(numbers)
    for token in numbers:
        if "/" in token:
            numerator, denominator = token.split("/", 1)
            allowed.update({numerator, denominator})
    return allowed


def _anchor_terms(spec: FollowUpSpec) -> set[str]:
    """确定性追问内容的锚点：数学 token、数字与 facts 中文片段。

    问法至少要保留一个锚点，避免 LLM 把追问改写成“答案是什么”这类
    不含任何题目内容的问题。
    """
    source = f"{spec.expression} {spec.template_prompt}"
    terms = set(re.findall(r"[a-z]{2,}", _normalize(source)))
    terms.update(_number_texts(source))
    for value in spec.facts.values():
        normalized = _normalize(value)
        terms.update(_number_texts(normalized))
        for run in re.findall(r"[\u4e00-\u9fff]+", normalized):
            terms.update(
                run[index : index + 2]
                for index in range(len(run) - 1)
            )
    return {term for term in terms if term}


def build_follow_up_prompt(
    spec: FollowUpSpec, *, supplement: bool
) -> str:
    """构造 LLM 输入；只给确定性内容与问法模板。"""
    template = (
        spec.supplement_prompt if supplement else spec.template_prompt
    )
    payload = {
        "task": "rewrite_follow_up",
        "level": spec.level,
        "supplement": supplement,
        "deterministic_content": {
            "expression": spec.expression,
            "expected_value": spec.expected,
            "facts": dict(spec.facts),
        },
        "template_prompt": template,
        "constraints": [
            "保留全部数字与表达式",
            "不得出现最终答案",
            "只问一个问题",
            "不超过 120 字",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def validate_follow_up_wording(
    wording: FollowUpWording, spec: FollowUpSpec
) -> str | None:
    """检查问法是否只使用授权数学内容，返回拒绝原因或 None。"""
    prompt = wording.prompt.strip()
    if not prompt:
        return "问法为空"
    if len(prompt) > MAX_PROMPT_CHARS:
        return "问法过长"
    normalized = _normalize(prompt)
    allowed = _allowed_numbers(spec)
    actual = set(_number_texts(prompt))
    extra = sorted(actual - allowed)
    if extra:
        return f"出现未授权的数字：{','.join(extra)}"
    anchors = _anchor_terms(spec)
    if anchors and not any(anchor in normalized for anchor in anchors):
        return "未保留追问的数学内容"
    for forbidden in spec.forbidden_in_prompt:
        if _normalize(forbidden) in normalized:
            return f"包含答案泄露词：{forbidden}"
    expected = _numeric_value(spec.expected)
    if expected is not None:
        for token in actual:
            value = _numeric_value(token)
            if value is not None and value == expected:
                return "包含答案数值"
    return None


def generate_follow_up_wording(
    spec: FollowUpSpec,
    *,
    supplement: bool,
    client: FollowUpClient,
) -> tuple[FollowUpWording | None, str]:
    """调用模型生成问法并校验；失败时返回原因。"""
    try:
        raw = client.complete(
            SYSTEM_FOLLOW_UP,
            build_follow_up_prompt(spec, supplement=supplement),
        )
        wording = FollowUpWording.model_validate_json(raw)
    except Exception:
        return None, "llm_unavailable"
    reason = validate_follow_up_wording(wording, spec)
    if reason is not None:
        return None, f"llm_rejected:{reason}"
    return wording, ""
