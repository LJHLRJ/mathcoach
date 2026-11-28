"""智能练习册渲染：选题理由 + 复用 worksheet 题面与答案页。"""
from __future__ import annotations

from ..worksheet import (
    Worksheet,
    WorksheetItem,
    WorksheetSource,
    render_worksheet_markdown,
)
from .models import WorksheetPlan


def plan_to_worksheet(
    plan: WorksheetPlan,
    *,
    include_answers: bool = True,
    include_solutions: bool = False,
) -> Worksheet:
    """把选题计划映射成现有练习单结构，供预览与下载复用。"""
    items = tuple(
        WorksheetItem(
            exercise=item.exercise,
            card=item.card,
            card_name=item.card.name,
            course=item.card.course,
            source_label=item.reason_text or "智能组卷",
        )
        for item in plan.items
    )
    return Worksheet(
        title=plan.title,
        source=WorksheetSource.SMART_PLAN,
        source_label="智能组卷",
        items=items,
        include_answers=include_answers,
        include_solutions=include_solutions and include_answers,
        generated_at=plan.generated_at,
        notes=plan.notes,
    )


def render_plan_markdown(
    plan: WorksheetPlan,
    *,
    include_answers: bool = True,
    include_solutions: bool = False,
) -> str:
    """渲染带选题理由的 Markdown 练习册。"""
    worksheet = plan_to_worksheet(
        plan,
        include_answers=include_answers,
        include_solutions=include_solutions,
    )
    body = render_worksheet_markdown(worksheet)
    lines = ["## 选题理由", ""]
    for index, item in enumerate(plan.items, start=1):
        lines.append(
            f"{index}. **{item.exercise.id}**（{item.card.name}）："
            f"{item.reason_text}"
        )
    if plan.notes:
        lines.extend(["", *[f"- {note}" for note in plan.notes]])
    reasons = "\n".join(lines)
    return body.replace("## 题目", f"{reasons}\n\n## 题目", 1)
