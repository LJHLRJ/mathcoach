"""M17 Task 7：主题对比度与语义化静态检查。"""
import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".streamlit" / "config.toml"
APP_PATH = ROOT / "app.py"
LAYOUT_PATH = ROOT / "mathcoach" / "ui" / "layout.py"


def _channel(value: int) -> float:
    """将八位色值通道转换为线性亮度分量。"""
    channel = value / 255
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """计算颜色的相对亮度。"""
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    return (
        0.2126 * _channel(red)
        + 0.7152 * _channel(green)
        + 0.0722 * _channel(blue)
    )


def _contrast_ratio(foreground: str, background: str) -> float:
    """计算前景与背景的对比度。"""
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def _theme() -> dict[str, str]:
    """读取主题配置。"""
    return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))["theme"]


def test_body_text_contrast_meets_wcag_aa():
    """正文与背景对比度达到 WCAG AA。"""
    theme = _theme()

    assert _contrast_ratio(theme["textColor"], theme["backgroundColor"]) >= 4.5


def test_primary_color_contrast_meets_three_to_one():
    """主色与背景对比度达到三比一。"""
    theme = _theme()

    assert _contrast_ratio(theme["primaryColor"], theme["backgroundColor"]) >= 3.0


def _call_name(node: ast.AST) -> str | None:
    """取调用表达式的属性名。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def test_feedback_calls_have_icons_and_readable_text():
    """反馈调用带图标与可读文案。"""
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    feedback = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) in {"success", "error"}
    ]

    assert feedback
    for call in feedback:
        assert call.args, "反馈必须带可读文案"
        assert ast.unparse(call.args[0]).strip(), "反馈文案不能为空"

    rendered = [ast.unparse(call.args[0]) for call in feedback]
    assert any("ICON_CHECK" in text and "答对了" in text for text in rendered)
    assert any("ICON_ERROR" in text and "再看一眼提示" in text for text in rendered)


def test_card_title_uses_semantic_subheader():
    """卡片标题使用语义化 subheader。"""
    tree = ast.parse(LAYOUT_PATH.read_text(encoding="utf-8"))
    card_function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "card"
    )
    calls = [
        node for node in ast.walk(card_function) if isinstance(node, ast.Call)
    ]

    assert any(
        _call_name(call) == "subheader"
        and call.args
        and ast.unparse(call.args[0]) == "title"
        for call in calls
    )
    assert not any(_call_name(call) == "markdown" for call in calls)
