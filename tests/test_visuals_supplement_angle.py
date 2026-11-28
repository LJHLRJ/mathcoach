"""补角公式可视化：关于 y 轴对称、正弦相同与余弦相反。"""
import math

import pytest

from mathcoach.ui.visuals.supplement_angle import (
    build_supplement_angle_figure,
)


def _trace(figure, name: str):
    """按名称取 trace；缺失时直接失败。"""
    return next(trace for trace in figure.data if trace.name == name)


def _summary(figure) -> str:
    """取包含补角结论的主标注文本。"""
    return next(
        annotation.text
        for annotation in figure.layout.annotations
        if "补角 π−x" in annotation.text
    )


def test_points_are_symmetric_about_y_axis() -> None:
    """P 与 Q 的横坐标相反、纵坐标相同。"""
    figure = build_supplement_angle_figure(30.0)
    points = _trace(figure, "P 与 Q")
    radians = math.radians(30.0)

    assert float(points.x[0]) == pytest.approx(math.cos(radians))
    assert float(points.y[0]) == pytest.approx(math.sin(radians))
    assert float(points.x[1]) == pytest.approx(-math.cos(radians))
    assert float(points.y[1]) == pytest.approx(math.sin(radians))


def test_annotation_shows_sine_equality_and_cosine_opposite() -> None:
    """标注给出 sin 相同、cos 相反的结论。"""
    text = _summary(build_supplement_angle_figure(30.0))

    assert "sin(π−x) = sin x = 0.500" in text
    assert "cos(π−x) = −cos x = −0.866" in text


def test_ninety_degrees_is_its_own_mirror() -> None:
    """90° 时 P 与 Q 重合在 y 轴上。"""
    figure = build_supplement_angle_figure(90.0)
    points = _trace(figure, "P 与 Q")

    assert float(points.x[0]) == pytest.approx(0.0, abs=1e-9)
    assert float(points.x[1]) == pytest.approx(0.0, abs=1e-9)
    assert float(points.y[0]) == pytest.approx(1.0, abs=1e-9)
    assert float(points.y[1]) == pytest.approx(1.0, abs=1e-9)


def test_zero_degrees_mirrors_to_left() -> None:
    """0° 的补角落在 (−1, 0)。"""
    points = _trace(build_supplement_angle_figure(0.0), "P 与 Q")

    assert float(points.x[0]) == pytest.approx(1.0, abs=1e-9)
    assert float(points.x[1]) == pytest.approx(-1.0, abs=1e-9)
    assert float(points.y[1]) == pytest.approx(0.0, abs=1e-9)


def test_module_does_not_import_streamlit_at_top_level() -> None:
    """可视化模块在顶层保持与 Streamlit 解耦。"""
    import mathcoach.ui.visuals.supplement_angle as module

    assert "streamlit" not in module.__dict__
    assert "st" not in module.__dict__
