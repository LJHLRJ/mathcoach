"""余弦定理可视化：三角形、边角标注与高亮。"""
import pytest

from mathcoach.ui.visuals.cosine_rule import build_cosine_rule_figure


def _trace(figure, name: str):
    """按名称取 trace；缺失时直接失败。"""
    return next(trace for trace in figure.data if trace.name == name)


def _annotation(figure, needle: str) -> str:
    """取包含指定片段的标注文本。"""
    return next(
        annotation.text
        for annotation in figure.layout.annotations
        if needle in annotation.text
    )


def test_right_angle_gives_hypotenuse() -> None:
    """3-4-90° 的第三边为 5。"""
    text = _annotation(build_cosine_rule_figure(3.0, 4.0, 90.0), "c ≈")
    assert "5.000" in text


def test_triangle_vertices_follow_side_lengths() -> None:
    """C 在原点，A 在 x 轴，B 由夹角确定。"""
    triangle = _trace(build_cosine_rule_figure(3.0, 4.0, 90.0), "三角形")

    assert len(triangle.x) == 4
    assert triangle.x[1] == pytest.approx(4.0)
    assert triangle.y[2] == pytest.approx(3.0)
    texts = {
        annotation.text for annotation in build_cosine_rule_figure(
            3.0, 4.0, 90.0
        ).layout.annotations
    }
    assert {"A", "B", "C"} <= texts


def test_highlight_side_c_adds_trace() -> None:
    """高亮第三边时单独增加一条红色边。"""
    figure = build_cosine_rule_figure(3.0, 4.0, 90.0, highlight="side_c")
    side = _trace(figure, "边 c")

    assert side.line.color == "#DC3545"


def test_highlight_angle_uses_red_arc() -> None:
    """高亮夹角时角弧变红加粗。"""
    figure = build_cosine_rule_figure(3.0, 4.0, 60.0, highlight="angle")
    arc = _trace(figure, "角 C")

    assert arc.line.color == "#DC3545"


def test_highlight_minus_adds_note() -> None:
    """高亮减号项时出现对应说明。"""
    figure = build_cosine_rule_figure(5.0, 4.0, 60.0, highlight="minus")

    assert _annotation(figure, "关注减号项")
    assert "关注减号项" in " ".join(
        annotation.text for annotation in figure.layout.annotations
    )


def test_invalid_values_fall_back_without_error() -> None:
    """非法边长或角度不抛异常。"""
    figure = build_cosine_rule_figure(0.0, -1.0, 0.0)

    assert _trace(figure, "三角形") is not None
    assert _trace(figure, "角 C") is not None


def test_module_does_not_import_streamlit_at_top_level() -> None:
    """可视化模块在顶层保持与 Streamlit 解耦。"""
    import mathcoach.ui.visuals.cosine_rule as module

    assert "streamlit" not in module.__dict__
    assert "st" not in module.__dict__
