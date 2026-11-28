"""把练习单渲染为可打印 HTML 或 Markdown。

HTML 自带 A4 打印样式，不引用外部资源；所有动态文本先脱敏再转义。
"""
from __future__ import annotations

import html

from ..domain.models import Exercise, ExerciseKind
from ..safety.redlines import sanitize_text
from .builder import Worksheet, WorksheetItem

_KIND_LABELS = {
    ExerciseKind.CHOICE: "选择题",
    ExerciseKind.MULTI: "多选题",
    ExerciseKind.TRUEFALSE: "判断题",
    ExerciseKind.FILL: "填空题",
    ExerciseKind.EXPR: "表达式题",
    ExerciseKind.PROOF_ORDER: "排序题",
    ExerciseKind.FIND_ERROR: "找错题",
    ExerciseKind.MATCH: "配对题",
}
_TRUE_WORDS = frozenset({"true", "t", "1", "对", "正确", "是", "√"})
_OPTION_LABELS = "ABCDEFGH"
_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0;
  background: #fff;
  color: #1f2328;
  font-family: "Songti SC", "Noto Serif CJK SC", "Microsoft YaHei", serif;
  line-height: 1.65;
}
.sheet { max-width: 820px; margin: 0 auto; padding: 28px 32px 48px; }
h1 { font-size: 24px; text-align: center; margin: 0 0 8px; }
.meta { text-align: center; color: #555; font-size: 13px; margin: 0 0 4px; }
.hint { text-align: center; color: #777; font-size: 13px; margin: 0 0 18px; }
.name-line { display: flex; gap: 24px; font-size: 14px; margin: 12px 0 24px; }
.question {
  break-inside: avoid;
  page-break-inside: avoid;
  margin: 0 0 22px;
  padding: 0 0 18px;
  border-bottom: 1px dashed #c9ced6;
}
.q-head { display: flex; gap: 10px; align-items: baseline; }
.num { font-weight: 700; }
.q-meta { color: #666; font-size: 12px; }
.stem { margin: 6px 0 8px; white-space: pre-wrap; }
.options {
  list-style: none;
  padding: 0;
  margin: 4px 0 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 18px;
}
.options.single { grid-template-columns: 1fr; }
.options li { display: flex; gap: 8px; align-items: flex-start; }
.box {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 1px solid #333;
  margin-top: 5px;
  flex: 0 0 auto;
}
.tf { display: flex; gap: 28px; margin-top: 8px; }
.answer-lines { margin-top: 8px; }
.line { border-bottom: 1px solid #bbb; height: 28px; }
.answer-key { break-before: page; page-break-before: always; }
.answer-key h2 { font-size: 20px; border-bottom: 2px solid #333; padding-bottom: 6px; }
.answer { break-inside: avoid; margin: 0 0 12px; }
.answer .num { margin-right: 4px; }
.solution { color: #444; font-size: 13px; margin: 4px 0 0 22px; }
.empty { color: #777; }
footer { margin-top: 30px; color: #888; font-size: 12px; text-align: center; }
@page { size: A4; margin: 16mm; }
@media print {
  body { font-size: 12pt; }
  .sheet { max-width: none; padding: 0; }
  .question { border-bottom-color: #ddd; }
  a { color: inherit; text-decoration: none; }
}
""".strip()


def _safe(text: object) -> str:
    """脱敏后转成字符串。"""
    return sanitize_text(str(text))


def _html(text: object) -> str:
    """脱敏并做 HTML 转义。"""
    return html.escape(_safe(text), quote=True)


def _md(text: object) -> str:
    """脱敏并把尖括号转成 Markdown 实体。"""
    return _safe(text).replace("<", "&lt;").replace(">", "&gt;")


def _kind_label(kind: ExerciseKind) -> str:
    """题型中文名。"""
    return _KIND_LABELS.get(kind, kind.value)


def _answer_text(exercise: Exercise) -> str:
    """答案展示文本；判断题统一显示为对/错。"""
    value = exercise.answer.strip()
    if exercise.kind is ExerciseKind.TRUEFALSE:
        return "对" if value.lower() in _TRUE_WORDS else "错"
    return value


def _meta_text(item: WorksheetItem) -> str:
    """题目上方的来源信息。"""
    return " · ".join(
        part
        for part in (
            item.course,
            item.card_name,
            _kind_label(item.exercise.kind),
        )
        if part
    )


def _question_html(index: int, item: WorksheetItem) -> list[str]:
    """渲染一道题的 HTML 片段。"""
    exercise = item.exercise
    lines = [
        '<section class="question">',
        '<div class="q-head">'
        f'<span class="num">{index}.</span>'
        f'<span class="q-meta">{_html(_meta_text(item))}</span>'
        "</div>",
        f'<div class="stem">{_html(exercise.stem)}</div>',
    ]
    if exercise.options:
        single = any(len(option) > 36 for option in exercise.options)
        class_name = "options single" if single else "options"
        lines.append(f'<ul class="{class_name}">')
        for position, option in enumerate(exercise.options):
            label = (
                _OPTION_LABELS[position]
                if position < len(_OPTION_LABELS)
                else str(position + 1)
            )
            lines.append(
                f'<li><span class="box"></span>'
                f"{label}. {_html(option)}</li>"
            )
        lines.append("</ul>")
    elif exercise.kind is ExerciseKind.TRUEFALSE:
        lines.append(
            '<div class="tf">'
            '<span class="box"></span>对'
            '<span class="box"></span>错'
            "</div>"
        )
    else:
        lines.append('<div class="answer-lines">')
        lines.extend('<div class="line"></div>' for _ in range(3))
        lines.append("</div>")
    lines.append("</section>")
    return lines


def _answer_html(
    index: int, item: WorksheetItem, include_solution: bool
) -> list[str]:
    """渲染答案页的一条答案。"""
    lines = [
        '<div class="answer">',
        f'<span class="num">{index}.</span> '
        f"<strong>答案：{_html(_answer_text(item.exercise))}</strong>",
    ]
    if include_solution and item.exercise.solution_outline:
        lines.append(
            f'<div class="solution">思路：'
            f"{_html(item.exercise.solution_outline)}</div>"
        )
    lines.append("</div>")
    return lines


def render_worksheet_html(worksheet: Worksheet) -> str:
    """渲染可打印的独立 HTML 文件。"""
    generated = worksheet.generated_at.astimezone().strftime("%Y-%m-%d %H:%M")
    hint = (
        "先独立完成，再对照答案页。"
        if worksheet.include_answers
        else "先独立完成。"
    )
    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_html(worksheet.title)}</title>",
        "<style>",
        _CSS,
        "</style>",
        "</head>",
        "<body>",
        '<main class="sheet">',
        f"<h1>{_html(worksheet.title)}</h1>",
        f'<p class="meta">{_html(worksheet.source_label)} · '
        f"共 {worksheet.count} 题 · 生成时间 {_html(generated)}</p>",
        f'<p class="hint">{_html(hint)}</p>',
        '<div class="name-line"><span>姓名：__________</span>'
        "<span>日期：__________</span></div>",
    ]
    if not worksheet.items:
        parts.append('<p class="empty">暂无可生成的题目。</p>')
    for index, item in enumerate(worksheet.items, start=1):
        parts.extend(_question_html(index, item))
        parts.append("")
    if worksheet.include_answers and worksheet.items:
        parts.append('<section class="answer-key">')
        parts.append("<h2>答案页</h2>")
        for index, item in enumerate(worksheet.items, start=1):
            parts.extend(
                _answer_html(index, item, worksheet.include_solutions)
            )
        parts.append("</section>")
    parts.append(f"<footer>由 Math Coach 生成 · {_html(generated)}</footer>")
    parts.extend(["</main>", "</body>", "</html>"])
    return "\n".join(parts)


def _question_markdown(index: int, item: WorksheetItem) -> list[str]:
    """渲染一道题的 Markdown 片段。"""
    exercise = item.exercise
    lines = [
        f"### {index}. {_md(exercise.stem)}",
        "",
        f"（{_md(_meta_text(item))}）",
        "",
    ]
    if exercise.options:
        for position, option in enumerate(exercise.options):
            label = (
                _OPTION_LABELS[position]
                if position < len(_OPTION_LABELS)
                else str(position + 1)
            )
            lines.append(f"- [ ] {label}. {_md(option)}")
    elif exercise.kind is ExerciseKind.TRUEFALSE:
        lines.append("- [ ] 对")
        lines.append("- [ ] 错")
    else:
        lines.extend(["答：", "", "____", "", "____"])
    lines.append("")
    return lines


def render_worksheet_markdown(worksheet: Worksheet) -> str:
    """渲染 Markdown 练习单，供预览与文本下载。"""
    generated = worksheet.generated_at.astimezone().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# {worksheet.title}",
        "",
        f"- 来源：{_md(worksheet.source_label)}",
        f"- 题数：{worksheet.count}",
        f"- 生成时间：{_md(generated)}",
        "",
        "姓名：__________　日期：__________",
        "",
        (
            "先独立完成，再对照答案页。"
            if worksheet.include_answers
            else "先独立完成。"
        ),
        "",
        "## 题目",
        "",
    ]
    if not worksheet.items:
        lines.append("暂无可生成的题目。")
    for index, item in enumerate(worksheet.items, start=1):
        lines.extend(_question_markdown(index, item))
    if worksheet.include_answers and worksheet.items:
        lines.extend(["---", "", "## 答案页", ""])
        for index, item in enumerate(worksheet.items, start=1):
            lines.append(
                f"{index}. **答案：** {_md(_answer_text(item.exercise))}"
            )
            if worksheet.include_solutions and item.exercise.solution_outline:
                lines.append(
                    f"   思路：{_md(item.exercise.solution_outline)}"
                )
        lines.append("")
    lines.extend(["---", "", "由 Math Coach 生成。"])
    return "\n".join(lines)
