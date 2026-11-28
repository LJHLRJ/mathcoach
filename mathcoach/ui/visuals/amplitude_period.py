"""正弦型函数可视化：拖动 A 与 ω 查看振幅和周期。"""
from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

DEFAULT_AMPLITUDE = 2.0
DEFAULT_OMEGA = 1.0
SAMPLE_POINTS = 240
MAX_X = 4.0 * math.pi
_EPSILON = 1e-9


def build_wave_figure(
    amplitude: float = DEFAULT_AMPLITUDE,
    omega: float = DEFAULT_OMEGA,
    *,
    sample_points: int = SAMPLE_POINTS,
) -> go.Figure:
    """构造正弦型函数图。

    Args:
        amplitude: 解析式中的 A，可为负；振幅取 ``|A|``。
        omega: 解析式中的 ω；绝对值决定周期。
        sample_points: 曲线采样点数。

    Returns:
        含曲线、振幅边界与周期标注的 Plotly 图。
    """
    omega_safe = omega if abs(omega) > _EPSILON else DEFAULT_OMEGA
    amplitude_abs = abs(amplitude)
    period = 2.0 * math.pi / abs(omega_safe)
    xs = np.linspace(0.0, MAX_X, sample_points)
    ys = amplitude * np.sin(omega_safe * xs)
    limit = max(amplitude_abs, 0.5) + 1.0

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[0.0, MAX_X],
            y=[amplitude_abs, amplitude_abs],
            mode="lines",
            name="振幅上界",
            line={"color": "#94A3B8", "width": 1, "dash": "dash"},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0, MAX_X],
            y=[-amplitude_abs, -amplitude_abs],
            mode="lines",
            name="振幅下界",
            line={"color": "#94A3B8", "width": 1, "dash": "dash"},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            name="正弦曲线",
            line={"color": "#4F8BF9", "width": 3},
            hovertemplate="x=%{x:.3f}<br>y=%{y:.3f}<extra></extra>",
        )
    )
    figure.add_shape(
        type="line",
        x0=period,
        x1=period,
        y0=-limit,
        y1=limit,
        line={"color": "#7C3AED", "width": 1, "dash": "dash"},
        layer="below",
    )
    figure.add_annotation(
        x=period,
        y=0.0,
        text="T",
        showarrow=False,
        font={"size": 12, "color": "#7C3AED"},
        yshift=10,
    )

    figure.add_annotation(
        x=MAX_X * 0.02,
        y=limit * 0.94,
        xref="x",
        yref="y",
        xanchor="left",
        yanchor="top",
        showarrow=False,
        align="left",
        text=(
            f"A = {amplitude:g}，ω = {omega_safe:g}<br>"
            f"振幅 |A| = {amplitude_abs:.3f}<br>"
            f"周期 T = 2π/|ω| = {period:.3f}"
        ),
        bgcolor="rgba(255, 255, 255, 0.88)",
        bordercolor="#CBD5E1",
        borderwidth=1,
    )

    figure.update_layout(
        title="y = A sin(ωx)：振幅与周期",
        xaxis={
            "title": "x",
            "range": [0.0, MAX_X],
            "tickvals": [
                0.0,
                math.pi,
                2.0 * math.pi,
                3.0 * math.pi,
                4.0 * math.pi,
            ],
            "ticktext": ["0", "π", "2π", "3π", "4π"],
            "zeroline": True,
        },
        yaxis={
            "title": "y",
            "range": [-limit, limit],
            "zeroline": True,
        },
        height=400,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        showlegend=False,
        plot_bgcolor="white",
    )
    return figure


def render() -> None:
    """渲染可交互的振幅/周期图。"""
    # 延迟导入：模块顶层保持无 Streamlit 依赖，便于纯函数测试
    import streamlit as st

    amplitude = st.slider(
        "A（振幅系数）",
        min_value=-3.0,
        max_value=3.0,
        value=DEFAULT_AMPLITUDE,
        step=0.5,
    )
    omega = st.slider(
        "ω（角频率）",
        min_value=0.5,
        max_value=3.0,
        value=DEFAULT_OMEGA,
        step=0.5,
    )
    st.plotly_chart(
        build_wave_figure(float(amplitude), float(omega)),
        width="stretch",
    )
    st.caption(
        "A 控制纵向伸缩，ω 控制横向伸缩；"
        "振幅取 |A|，周期为 2π/|ω|。"
    )
