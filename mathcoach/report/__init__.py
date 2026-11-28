"""可解释学情报告：统计层结论 + 记录 ID 证据 + 受限叙事。"""
from .builder import build_explainable_report
from .models import (
    EvidenceAnchor,
    ExplainableReport,
    ReportConclusion,
    ReportMetric,
)
from .narrative import (
    PROMPT_VERSION,
    NarrativeSection,
    ReportClient,
    ReportNarrative,
    build_report_client,
    build_report_prompt,
    generate_report_narrative,
    render_narrative_markdown,
    validate_report_narrative,
)
from .render import render_report_markdown

__all__ = [
    "PROMPT_VERSION",
    "EvidenceAnchor",
    "ExplainableReport",
    "NarrativeSection",
    "ReportClient",
    "ReportConclusion",
    "ReportMetric",
    "ReportNarrative",
    "build_explainable_report",
    "build_report_client",
    "build_report_prompt",
    "generate_report_narrative",
    "render_narrative_markdown",
    "render_report_markdown",
    "validate_report_narrative",
]
