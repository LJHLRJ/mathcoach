"""报告 LLM 叙事：只改写措辞，结论与数字受统计层白名单约束。"""
from __future__ import annotations

import json
import re
import unicodedata
from fractions import Fraction
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict

from .models import ExplainableReport, ReportConclusion
from .render import render_report_markdown

PROMPT_VERSION = "report-narrative-1"
MAX_SECTION_CHARS = 160
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")
_CAUSAL_MARKERS = ("因为", "所以", "导致", "由于", "因此")

SYSTEM_REPORT = (
    f"prompt_version={PROMPT_VERSION} 你只改写学情报告的措辞。"
    "必须为给定的每个 conclusion_id 输出一段话，不得新增或删除结论；"
    "不得新增数字、卡片、知识点或因果判断；只能使用给出的指标。"
    "只输出 JSON，格式为 {\"sections\":[{\"conclusion_id\":\"...\","
    "\"text\":\"...\"}]}。"
)


class ReportClient(Protocol):
    """报告叙事所需的最小模型客户端。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """返回模型原始文本，期望为 JSON。"""
        ...


class NarrativeSection(BaseModel):
    """一段与结论绑定的改写文案。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conclusion_id: str
    text: str


class ReportNarrative(BaseModel):
    """LLM 返回的完整叙事。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sections: tuple[NarrativeSection, ...]


def build_report_client(provider: object) -> ReportClient | None:
    """从 Provider 提取带 ``complete`` 的报告客户端。"""
    complete = getattr(provider, "complete", None)
    if callable(complete):
        return cast(ReportClient, provider)
    return None


def _normalize(text: str) -> str:
    """统一全角、大小写与负号。"""
    return (
        unicodedata.normalize("NFKC", text)
        .lower()
        .replace("−", "-")
    )


def _numbers(text: str) -> set[Fraction]:
    """提取可解析的数字/分数。"""
    values: set[Fraction] = set()
    for token in _NUMBER.findall(_normalize(text)):
        try:
            values.add(Fraction(token))
        except (ValueError, ZeroDivisionError):
            continue
    return values


def _allowed_numbers(conclusion: ReportConclusion) -> set[Fraction]:
    """允许在叙事中出现的数字：结论原句与指标值。"""
    allowed = _numbers(conclusion.statement)
    for metric in conclusion.metrics:
        allowed.add(Fraction(str(metric.value)))
        if metric.unit in {"概率", "比例"}:
            allowed.add(Fraction(str(metric.value * 100)))
        allowed.update(_numbers(metric.label))
    return allowed


def build_report_prompt(report: ExplainableReport) -> str:
    """构造 LLM 输入；只给统计层已有结论与指标。"""
    payload = {
        "task": "rewrite_report_narrative",
        "prompt_version": PROMPT_VERSION,
        "conclusions": [
            {
                "conclusion_id": conclusion.id,
                "statement": conclusion.statement,
                "metrics": [
                    {
                        "id": metric.id,
                        "label": metric.label,
                        "value": metric.value,
                        "unit": metric.unit,
                    }
                    for metric in conclusion.metrics
                ],
                "evidence_count": len(conclusion.evidence),
            }
            for conclusion in report.conclusions
        ],
        "constraints": [
            "每个 conclusion_id 输出一段，不得增删结论",
            "不得新增数字、卡片、知识点或因果判断",
            "每条不超过 120 字",
            "只输出 JSON sections",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def validate_report_narrative(
    narrative: ReportNarrative, report: ExplainableReport
) -> str | None:
    """检查叙事是否只改写统计层已有结论，返回拒绝原因或 None。"""
    expected = [conclusion.id for conclusion in report.conclusions]
    actual = [section.conclusion_id for section in narrative.sections]
    if sorted(actual) != sorted(expected):
        return "结论集合不一致"
    if len(set(actual)) != len(actual):
        return "结论重复"
    by_id = {
        conclusion.id: conclusion for conclusion in report.conclusions
    }
    for section in narrative.sections:
        text = section.text.strip()
        if not text:
            return "叙事为空"
        if len(text) > MAX_SECTION_CHARS:
            return "叙事过长"
        if any(marker in text for marker in _CAUSAL_MARKERS):
            return "包含因果判断"
        conclusion = by_id[section.conclusion_id]
        allowed = _allowed_numbers(conclusion)
        numbers = _numbers(text)
        extra = numbers - allowed
        if extra:
            return f"出现未授权数字：{','.join(str(item) for item in extra)}"
        required = _numbers(conclusion.statement)
        if required and not (numbers & required):
            return "缺少统计层数字"
    return None


def generate_report_narrative(
    report: ExplainableReport,
    *,
    client: ReportClient,
) -> tuple[ReportNarrative | None, str]:
    """调用模型生成受限叙事；失败时返回原因供模板回退。"""
    if not report.conclusions:
        return None, "no_conclusions"
    try:
        raw = client.complete(SYSTEM_REPORT, build_report_prompt(report))
        narrative = ReportNarrative.model_validate_json(raw)
    except Exception:
        return None, "llm_unavailable"
    reason = validate_report_narrative(narrative, report)
    if reason is not None:
        return None, f"llm_rejected:{reason}"
    return narrative, ""


def render_narrative_markdown(
    report: ExplainableReport, narrative: ReportNarrative
) -> str:
    """用受限叙事替换结论标题，证据仍来自统计层。"""
    statements = {
        section.conclusion_id: section.text
        for section in narrative.sections
    }
    return render_report_markdown(report, statements=statements)
