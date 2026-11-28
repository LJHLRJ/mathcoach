"""可解释报告的模板叙事：只组织已有结论，不新增判断。"""
from __future__ import annotations

from collections.abc import Mapping

from .models import ExplainableReport


def render_report_markdown(
    report: ExplainableReport,
    *,
    statements: Mapping[str, str] | None = None,
) -> str:
    """把报告渲染成 Markdown；结论与证据一一对应。

    Args:
        report: 统计层报告。
        statements: 可选的结论 ID -> 展示文案；用于 LLM 受限改写。
    """
    lines = ["## 结论与证据", ""]
    if not report.conclusions:
        for note in report.notes or ("近 7 天证据不足，暂不生成结论。",):
            lines.append(f"- {note}")
        return "\n".join(lines).strip()
    overrides = statements or {}
    for conclusion in report.conclusions:
        statement = overrides.get(conclusion.id, conclusion.statement)
        lines.append(f"### {statement}")
        if conclusion.metrics:
            for metric in conclusion.metrics:
                lines.append(
                    f"- {metric.label}：{metric.value:g}{metric.unit}"
                )
        if conclusion.evidence:
            lines.append("- 证据：")
            for anchor in conclusion.evidence:
                lines.append(
                    f"  - `{anchor.kind}:{anchor.id}` · "
                    f"{anchor.occurred_at:%Y-%m-%d} · {anchor.snippet}"
                )
        else:
            lines.append("- 证据：暂无直接作答记录。")
        for gap in conclusion.data_gaps:
            lines.append(f"- 数据缺口：{gap}")
        lines.append("")
    return "\n".join(lines).strip()
