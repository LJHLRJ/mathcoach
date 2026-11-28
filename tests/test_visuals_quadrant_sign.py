"""象限符号可视化：象限判定、符号标注与轴线角。"""
import math

import pytest

from mathcoach.ui.visuals.quadrant_sign import (
    build_quadrant_sign_figure,
    quadrant_name,
)


def _trace(figure, name: str):
    """按名称取 trace；缺失时直接失败。"""
    return next(trace for trace in figure.data if trace.name == name)


def _summary(figure) -> str:
    """取包含象限结论的主标注文本。"""
    return next(
        annotation.text
        for annotation in figure.layout.annotations
        if "所在象限" in annotation.text
    )


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [
        (30.0, "第一象限"),
        (120.0, "第二象限"),
        (210.0, "第三象限"),
        (300.0, "第四象限"),
        (90.0, "坐标轴上"),
        (180.0, "坐标轴上"),
        (360.0, "坐标轴上"),
    ],
)
def test_quadrant_name(degrees: float, expected: str) -> None:
    """四个象限与轴线角都能正确命名。"""
    assert quadrant_name(degrees) == expected


def test_second_quadrant_has_positive_sin_and_negative_cos() -> None:
    """第二象限标注正弦为正、余弦为负。"""
    text = _summary(build_quadrant_sign_figure(120.0))

    assert "第二象限" in text
    assert "sin x = +0.866" in text
    assert "cos x = −0.500" in text


def test_point_uses_cos_and_sin() -> None:
    """点 P 的坐标等于所选角度的 cos 与 sin。"""
    point = _trace(build_quadrant_sign_figure(120.0), "点 P")

    assert float(point.x[0]) == pytest.approx(
        math.cos(math.radians(120.0))
    )
    assert float(point.y[0]) == pytest.approx(
        math.sin(math.radians(120.0))
    )


def test_four_quadrant_backgrounds_and_labels() -> None:
    """四象限使用四块底色并带符号说明。"""
    figure = build_quadrant_sign_figure(120.0)

    assert len(figure.layout.shapes) == 4
    labels = " ".join(
        annotation.text for annotation in figure.layout.annotations
    )
    assert "sin+ cos+" in labels
    assert "sin+ cos−" in labels
    assert "sin− cos−" in labels
    assert "sin− cos+" in labels


def test_axis_angle_reports_zero() -> None:
    """轴线角单独命名，余弦显示为 0。"""
    figure = build_quadrant_sign_figure(90.0)
    text = _summary(figure)
    point = _trace(figure, "点 P")

    assert "坐标轴上" in text
    assert "cos x = 0.000" in text
    assert float(point.x[0]) == pytest.approx(0.0, abs=1e-9)
    assert float(point.y[0]) == pytest.approx(1.0, abs=1e-9)


def test_module_does_not_import_streamlit_at_top_level() -> None:
    """可视化模块在顶层保持与 Streamlit 解耦。"""
    import mathcoach.ui.visuals.quadrant_sign as module

    assert "streamlit" not in module.__dict__
    assert "st" not in module.__dict__
