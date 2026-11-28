"""正弦型函数可视化：振幅、周期与负振幅。"""
import math

import pytest

from mathcoach.ui.visuals.amplitude_period import build_wave_figure


def _trace(figure, name: str):
    """按名称取 trace；缺失时直接失败。"""
    return next(trace for trace in figure.data if trace.name == name)


def _summary(figure) -> str:
    """取包含 A 与 ω 的主标注文本。"""
    return next(
        annotation.text
        for annotation in figure.layout.annotations
        if "振幅" in annotation.text
    )


def test_curve_reaches_amplitude_and_period_marker() -> None:
    """曲线的最大值等于振幅，周期标记落在 T=π。"""
    figure = build_wave_figure(3.0, 2.0)
    curve = _trace(figure, "正弦曲线")

    assert max(float(value) for value in curve.y) == pytest.approx(
        3.0, abs=0.01
    )
    assert float(figure.layout.shapes[0].x0) == pytest.approx(math.pi)
    assert float(figure.layout.shapes[0].x1) == pytest.approx(math.pi)


def test_summary_shows_amplitude_and_period() -> None:
    """标注显示 |A| 与 2π/|ω| 的数值。"""
    text = _summary(build_wave_figure(3.0, 2.0))

    assert "振幅 |A| = 3.000" in text
    assert "周期 T = 2π/|ω| = 3.142" in text


def test_negative_amplitude_uses_absolute_value() -> None:
    """负的 A 仍按 |A| 计算振幅。"""
    figure = build_wave_figure(-2.0, 1.0)
    upper = _trace(figure, "振幅上界")
    text = _summary(figure)

    assert float(upper.y[0]) == pytest.approx(2.0)
    assert "振幅 |A| = 2.000" in text


def test_zero_omega_falls_back_without_error() -> None:
    """ω=0 时回退到默认角频率，避免除零。"""
    text = _summary(build_wave_figure(2.0, 0.0))

    assert "周期 T = 2π/|ω| = 6.283" in text


def test_module_does_not_import_streamlit_at_top_level() -> None:
    """可视化模块在顶层保持与 Streamlit 解耦。"""
    import mathcoach.ui.visuals.amplitude_period as module

    assert "streamlit" not in module.__dict__
    assert "st" not in module.__dict__
