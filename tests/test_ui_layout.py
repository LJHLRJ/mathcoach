"""M17 Task 2：布局辅助函数单测。"""
import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
LAYOUT_PATH = ROOT / "mathcoach" / "ui" / "layout.py"
BANNED_LAYERS = (
    "mathcoach.domain",
    "mathcoach.session",
    "mathcoach.memory",
    "mathcoach.safety",
    "domain",
    "session",
    "memory",
    "safety",
)


def _run(body: str) -> AppTest:
    """在 AppTest 脚本上下文内调用布局函数。"""
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "import streamlit as st\n"
        "from mathcoach.ui.layout import card, hint_block, kpi_row\n"
        f"{body}\n"
    )
    at = AppTest.from_string(script, default_timeout=15)
    at.run()
    assert not at.exception
    return at


def test_card_renders_title_caption_and_body():
    at = _run('with card("目标确认", "第一步"):\n    st.write("卡片正文")\n')

    assert at.subheader[0].value == "目标确认"
    assert at.caption[0].value == "第一步"
    assert any("卡片正文" in markdown.value for markdown in at.markdown)


def test_card_without_caption_renders_no_caption():
    at = _run('with card("讲解 · 函数"):\n    st.write("正文")\n')

    assert at.subheader[0].value == "讲解 · 函数"
    assert not at.caption


def test_kpi_row_renders_one_metric_per_item():
    at = _run(
        'kpi_row([("当前卡片", "函数"), ("课程", "函数与导数"), ("难度", "入门")])\n'
    )

    assert [metric.label for metric in at.metric] == ["当前卡片", "课程", "难度"]
    assert [metric.value for metric in at.metric] == ["函数", "函数与导数", "入门"]


def test_hint_block_renders_level_caption_and_info():
    at = _run('hint_block(2, "先回忆定义域")\n')

    assert at.caption[0].value == "提示层级 L2"
    assert at.info[0].value == "先回忆定义域"


def test_layout_module_does_not_import_business_layers():
    tree = ast.parse(LAYOUT_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for name in imported:
        assert not name.startswith(BANNED_LAYERS), f"layout.py 不应依赖业务层：{name}"


def test_math_markdown_wraps_caret_and_underscore_formulas():
    from mathcoach.ui.layout import math_markdown

    assert math_markdown("求 x^2 的导数") == "求 $x^2$ 的导数"
    assert math_markdown("a_{ij} 与 b^T") == "$a_{ij}$ 与 $b^T$"
    assert math_markdown("已有 $x^2$ 不再处理") == "已有 $x^2$ 不再处理"
