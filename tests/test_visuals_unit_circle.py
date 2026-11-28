"""单位圆可视化：端点坐标、投影线段、平方和标注与 Streamlit 解耦。"""
import math

import pytest

from mathcoach.ui.visuals.unit_circle import build_unit_circle_figure


def _trace(figure, name: str):
    """按名称取 trace；缺失时直接失败。"""
    return next(trace for trace in figure.data if trace.name == name)


def test_point_uses_cos_and_sin() -> None:
    """点 P 的坐标等于所选角度的 cos 与 sin。"""
    figure = build_unit_circle_figure(30.0)

    point = _trace(figure, "点 P")
    cos_value = math.cos(math.radians(30.0))
    sin_value = math.sin(math.radians(30.0))
    assert float(point.x[0]) == pytest.approx(cos_value)
    assert float(point.y[0]) == pytest.approx(sin_value)


def test_projection_lines_follow_point() -> None:
    """cos 投影落在 x 轴，sin 投影从 x 轴连到点 P。"""
    figure = build_unit_circle_figure(30.0)

    cos_line = _trace(figure, "cos x")
    sin_line = _trace(figure, "sin x")
    cos_value = math.cos(math.radians(30.0))
    sin_value = math.sin(math.radians(30.0))
    assert list(cos_line.y) == [0.0, 0.0]
    assert float(cos_line.x[1]) == pytest.approx(cos_value)
    assert float(sin_line.x[0]) == pytest.approx(cos_value)
    assert float(sin_line.x[1]) == pytest.approx(cos_value)
    assert float(sin_line.y[1]) == pytest.approx(sin_value)


@pytest.mark.parametrize(
    ("degrees", "expected_x", "expected_y"),
    [
        (0.0, 1.0, 0.0),
        (90.0, 0.0, 1.0),
        (180.0, -1.0, 0.0),
        (270.0, 0.0, -1.0),
        (360.0, 1.0, 0.0),
    ],
)
def test_axis_endpoints_have_no_float_noise(
    degrees: float, expected_x: float, expected_y: float
) -> None:
    """特殊角端点不出现 6e-17 之类的浮点噪声。"""
    point = _trace(build_unit_circle_figure(degrees), "点 P")

    assert float(point.x[0]) == pytest.approx(expected_x, abs=1e-9)
    assert float(point.y[0]) == pytest.approx(expected_y, abs=1e-9)


def test_annotation_and_title_show_square_sum() -> None:
    """标注与标题都显示平方和为 1。"""
    figure = build_unit_circle_figure(37.0)

    assert "cos²x + sin²x = 1.000" in figure.layout.annotations[0].text
    assert "sin²x + cos²x = 1.000" in figure.layout.title.text


def test_module_does_not_import_streamlit_at_top_level() -> None:
    """可视化模块在顶层保持与 Streamlit 解耦。"""
    import mathcoach.ui.visuals.unit_circle as unit_circle

    assert "streamlit" not in unit_circle.__dict__
    assert "st" not in unit_circle.__dict__
