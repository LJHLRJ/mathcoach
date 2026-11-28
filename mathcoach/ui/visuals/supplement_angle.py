"""补角公式可视化：x 与 π−x 的终边关于 y 轴对称。"""
from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

DEFAULT_DEGREES = 30.0
CIRCLE_POINTS = 180
AXIS_LIMIT = 1.35
_EPSILON = 1e-9


def _clean(value: float) -> float:
    """把浮点噪声归零，避免 180° 时出现 6e-17。"""
    return 0.0 if abs(value) < _EPSILON else value


def _format_value(value: float) -> str:
    """格式化三位小数，负数使用数学减号。"""
    if abs(value) < _EPSILON:
        return "0.000"
    prefix = "−" if value < 0 else ""
    return f"{prefix}{abs(value):.3f}"


def build_supplement_angle_figure(
    degrees: float = DEFAULT_DEGREES,
    *,
    circle_points: int = CIRCLE_POINTS,
) -> go.Figure:
    """构造补角公式图。

    Args:
        degrees: 原角 x，建议范围 0°–180°。
        circle_points: 单位圆采样点数。

    Returns:
        含 P、Q、对称轴与正弦/余弦对照标注的 Plotly 图。
    """
    angle = degrees % 360.0
    radians = math.radians(angle)
    mirror_radians = math.pi - radians
    mirror_degrees = (180.0 - angle) % 360.0

    cos_value = _clean(math.cos(radians))
    sin_value = _clean(math.sin(radians))
    mirror_cos = _clean(math.cos(mirror_radians))
    mirror_sin = _clean(math.sin(mirror_radians))

    angles = np.linspace(0.0, 2.0 * math.pi, circle_points)
    arc_angles = np.linspace(
        0.0, radians, max(2, circle_points // 4)
    )
    mirror_arc = np.linspace(
        0.0, mirror_radians, max(2, circle_points // 4)
    )

    figure = go.Figure()
    figure.add_shape(
        type="line",
        x0=0.0,
        x1=0.0,
        y0=-1.1,
        y1=1.1,
        line={"color": "#94A3B8", "width": 1, "dash": "dash"},
        layer="below",
    )
    figure.add_trace(
        go.Scatter(
            x=np.cos(angles),
            y=np.sin(angles),
            mode="lines",
            name="单位圆",
            line={"color": "#94A3B8", "width": 2},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0, cos_value],
            y=[0.0, 0.0],
            mode="lines",
            name="cos x",
            line={"color": "#4F8BF9", "width": 4},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[cos_value, cos_value],
            y=[0.0, sin_value],
            mode="lines",
            name="sin x",
            line={"color": "#DC3545", "width": 4},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0, mirror_cos],
            y=[0.0, 0.0],
            mode="lines",
            name="补角 cos",
            line={"color": "#F59E0B", "width": 3, "dash": "dot"},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[mirror_cos, mirror_cos],
            y=[0.0, mirror_sin],
            mode="lines",
            name="补角 sin",
            line={"color": "#F59E0B", "width": 3, "dash": "dot"},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0, cos_value],
            y=[0.0, sin_value],
            mode="lines",
            name="半径 OP",
            line={"color": "#0F172A", "width": 2, "dash": "dash"},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0, mirror_cos],
            y=[0.0, mirror_sin],
            mode="lines",
            name="半径 OQ",
            line={"color": "#7C3AED", "width": 2, "dash": "dash"},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=0.26 * np.cos(arc_angles),
            y=0.26 * np.sin(arc_angles),
            mode="lines",
            name="角 x",
            line={"color": "#7C3AED", "width": 2},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=0.26 * np.cos(mirror_arc),
            y=0.26 * np.sin(mirror_arc),
            mode="lines",
            name="补角 π−x",
            line={"color": "#F59E0B", "width": 2},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[cos_value, mirror_cos],
            y=[sin_value, mirror_sin],
            mode="markers+text",
            name="P 与 Q",
            marker={"size": 10, "color": ["#0F172A", "#F59E0B"]},
            text=[
                f"P({cos_value:.3f}, {sin_value:.3f})",
                f"Q({mirror_cos:.3f}, {mirror_sin:.3f})",
            ],
            textposition="top center",
            hovertemplate="(%{x:.3f}, %{y:.3f})<extra></extra>",
        )
    )

    figure.add_annotation(
        x=-AXIS_LIMIT + 0.05,
        y=AXIS_LIMIT - 0.05,
        xref="x",
        yref="y",
        xanchor="left",
        yanchor="top",
        showarrow=False,
        align="left",
        text=(
            f"角 x = {angle:g}°，补角 π−x = {mirror_degrees:g}°<br>"
            f"sin(π−x) = sin x = {_format_value(mirror_sin)}<br>"
            f"cos(π−x) = −cos x = {_format_value(mirror_cos)}"
        ),
        bgcolor="rgba(255, 255, 255, 0.88)",
        bordercolor="#CBD5E1",
        borderwidth=1,
    )

    figure.update_layout(
        title="补角公式：关于 y 轴对称",
        xaxis={
            "title": "cos x",
            "range": [-AXIS_LIMIT, AXIS_LIMIT],
            "zeroline": True,
            "scaleanchor": "y",
            "scaleratio": 1,
        },
        yaxis={
            "title": "sin x",
            "range": [-AXIS_LIMIT, AXIS_LIMIT],
            "zeroline": True,
        },
        height=430,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        showlegend=False,
        plot_bgcolor="white",
    )
    return figure


def render() -> None:
    """渲染可交互的补角公式图。"""
    # 延迟导入：模块顶层保持无 Streamlit 依赖，便于纯函数测试
    import streamlit as st

    degrees = st.slider(
        "原角 x（度）",
        min_value=0,
        max_value=180,
        value=int(DEFAULT_DEGREES),
        step=1,
    )
    st.plotly_chart(
        build_supplement_angle_figure(float(degrees)), width="stretch"
    )
    st.caption(
        "π−x 与 x 的终边关于 y 轴对称：正弦相同，余弦互为相反数。"
    )
