"""步骤判定展示：把步骤结果映射成行级徽标与原因，不参与判定。"""
from __future__ import annotations

from dataclasses import dataclass

from .error_map import step_error_type
from .models import StepAttempt, StepSpec, StepVerdict

_TAG_LABELS = {
    "formula": "公式",
    "calculation": "计算",
    "sign": "符号/正负",
    "identity": "恒等式",
    "conversion": "换算",
    "value": "取值",
    "procedure": "解题步骤",
    "order": "顺序",
}

_INPUT_HINTS = {
    "expr": "数学表达式，如 3*x**2",
    "number": "数字，如 2 或 3/5",
    "sign": "文字或符号，如 减去 / +",
    "order": "步骤序号，用逗号分隔，如 1,2,3",
    "pair": "配对，如 A=1;B=2",
}


@dataclass(frozen=True)
class StepMarker:
    """行级展示信息；``tone`` 对应 Streamlit 的 success/error/info。"""

    tone: str
    label: str
    reason: str


_MARKERS = {
    StepVerdict.CORRECT: StepMarker(
        "success", "正确", "这一步的结果与期望一致。"
    ),
    StepVerdict.INCORRECT: StepMarker(
        "error", "这一步不对", "这一步的结果与期望不一致。"
    ),
    StepVerdict.UNVERIFIABLE: StepMarker(
        "info", "无法自动核对", "符号验证超时或无法确认，建议人工核对。"
    ),
    StepVerdict.REJECTED: StepMarker(
        "info", "输入不符合格式", "只接受白名单内的数字或数学表达式。"
    ),
    StepVerdict.OUT_OF_SCOPE: StepMarker(
        "info", "超出步骤范围", "这一步不在当前题目的步骤元数据中。"
    ),
}


def present_verdict(verdict: StepVerdict) -> StepMarker:
    """返回步骤判定的行级展示信息。"""
    return _MARKERS.get(verdict, _MARKERS[StepVerdict.OUT_OF_SCOPE])


def step_tag_label(tag: str) -> str:
    """把 step_tag 转成中文说明。"""
    return _TAG_LABELS.get(tag, tag or "未标注")


def input_kind_hint(kind: str) -> str:
    """返回该步骤期望的输入格式说明。"""
    return _INPUT_HINTS.get(kind, "按题目要求填写")


def build_step_reason(spec: StepSpec, attempt: StepAttempt) -> str:
    """构造“为什么这样判定”的说明；不展示标准答案。"""
    marker = present_verdict(attempt.verdict)
    lines = [
        f"- 这一步考的是：{step_tag_label(spec.step_tag)}",
        f"- 输入格式：{input_kind_hint(spec.input_kind)}",
        f"- 判定：{marker.reason}",
    ]
    if attempt.verdict is StepVerdict.INCORRECT:
        error_type = step_error_type(spec, attempt.verdict)
        if error_type is not None:
            lines.append(
                f"- 初步错因：{error_type.value}"
                f"（由这一步的「{step_tag_label(spec.step_tag)}」标签推断）"
            )
        lines.append(
            f"- 建议：回到「{step_tag_label(spec.step_tag)}」"
            "对应的概念，再检查一次。"
        )
    return "\n".join(lines)
