"""练习单渲染：打印结构、答案页开关、脱敏与转义。"""
from datetime import datetime, timezone

from mathcoach.domain.models import Exercise, ExerciseKind
from mathcoach.worksheet import (
    Worksheet,
    WorksheetItem,
    WorksheetSource,
    render_worksheet_html,
    render_worksheet_markdown,
)

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def _choice_item() -> WorksheetItem:
    """构造一道带选项与思路的题目。"""
    return WorksheetItem(
        exercise=Exercise(
            id="e1",
            card_id="c1",
            kind=ExerciseKind.CHOICE,
            stem="已知 <script>alert(1)</script>，联系电话 13800138000",
            answer="A",
            solution_outline="先看定义域",
            options=("选项一", "选项二"),
        ),
        card=None,
        card_name="测试卡",
        course="测试课程",
        source_label="错题",
    )


def _truefalse_item() -> WorksheetItem:
    """构造一道判断题。"""
    return WorksheetItem(
        exercise=Exercise(
            id="e2",
            card_id="c1",
            kind=ExerciseKind.TRUEFALSE,
            stem="两个定义域相同，则函数相同。",
            answer="True",
            solution_outline="",
        ),
        card=None,
        card_name="测试卡",
        course="测试课程",
        source_label="待复习",
    )


def _worksheet(
    *, include_answers: bool = True, include_solutions: bool = True
) -> Worksheet:
    """构造一份最小练习单。"""
    return Worksheet(
        title="数学练习单",
        source=WorksheetSource.MISTAKES,
        source_label="错题本",
        items=(_choice_item(), _truefalse_item()),
        include_answers=include_answers,
        include_solutions=include_solutions,
        generated_at=NOW,
    )


def test_html_has_print_structure_and_answer_key() -> None:
    """HTML 带 A4 打印样式与答案页。"""
    html = render_worksheet_html(_worksheet())

    assert html.startswith("<!DOCTYPE html>")
    assert "@page" in html
    assert "answer-key" in html
    assert "答案页" in html
    assert "答案：A" in html
    assert "思路：先看定义域" in html
    assert "答案：对" in html


def test_html_escapes_and_redacts_text() -> None:
    """HTML 转义尖括号并脱敏手机号。"""
    html = render_worksheet_html(_worksheet())

    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html
    assert "13800138000" not in html
    assert "[已脱敏]" in html


def test_html_can_omit_answers_and_solutions() -> None:
    """关闭答案页时不输出答案与答案页标题。"""
    html = render_worksheet_html(
        _worksheet(include_answers=False, include_solutions=False)
    )

    assert "答案页" not in html
    assert "答案：A" not in html
    assert "先独立完成。" in html


def test_html_keeps_answers_without_solutions() -> None:
    """只关思路时仍保留答案页。"""
    html = render_worksheet_html(
        _worksheet(include_answers=True, include_solutions=False)
    )

    assert "答案页" in html
    assert "答案：A" in html
    assert "思路：先看定义域" not in html


def test_markdown_has_questions_and_answer_key() -> None:
    """Markdown 包含题目、选项与答案页。"""
    markdown = render_worksheet_markdown(_worksheet())

    assert "# 数学练习单" in markdown
    assert "## 题目" in markdown
    assert "### 1." in markdown
    assert "- [ ] A." in markdown
    assert "- [ ] 对" in markdown
    assert "## 答案页" in markdown
    assert "**答案：** A" in markdown
    assert "思路：先看定义域" in markdown


def test_markdown_escapes_and_can_omit_answers() -> None:
    """Markdown 转义尖括号，并可关闭答案页。"""
    markdown = render_worksheet_markdown(
        _worksheet(include_answers=False, include_solutions=False)
    )

    assert "&lt;script&gt;" in markdown
    assert "## 答案页" not in markdown
    assert "**答案：**" not in markdown
