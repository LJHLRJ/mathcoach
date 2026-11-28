"""单位圆可视化：角度驱动，显示 sin/cos 投影与平方和；只渲染，不参与判定。"""
from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

DEFAULT_DEGREES = 40.0
CIRCLE_POINTS = 180
AXIS_LIMIT = 1.3
ARC_RADIUS = 0.28
_EPSILON = 1e-9


def _clean(value: float) -> float:
    """把浮点噪声归零，避免 90° 时显示 6e-17。"""
    return 0.0 if abs(value) < _EPSILON else value


def build_unit_circle_figure(
    degrees: float = DEFAULT_DEGREES,
    *,
    circle_points: int = CIRCLE_POINTS,
) -> go.Figure:
    """构造单位圆图。

    Args:
        degrees: 从 x 轴正方向逆时针旋转的角度（度）。
        circle_points: 单位圆采样点数。

    Returns:
        含单位圆、半径、sin/cos 投影、角度弧与点 P 的 Plotly 图。
    """
    radians = math.radians(degrees)
    cos_value = _clean(math.cos(radians))
    sin_value = _clean(math.sin(radians))

    angles = np.linspace(0.0, 2.0 * math.pi, circle_points)
    arc_angles = np.linspace(0.0, radians, max(2, circle_points // 4))

    figure = go.Figure()
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
            x=ARC_RADIUS * np.cos(arc_angles),
            y=ARC_RADIUS * np.sin(arc_angles),
            mode="lines",
            name="角 x",
            line={"color": "#7C3AED", "width": 2},
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[cos_value],
            y=[sin_value],
            mode="markers+text",
            name="点 P",
            marker={"size": 10, "color": "#0F172A"},
            text=[f"P({cos_value:.3f}, {sin_value:.3f})"],
            textposition="top center",
            hovertemplate="P(%{x:.3f}, %{y:.3f})<extra></extra>",
        )
    )

    square_sum = cos_value**2 + sin_value**2
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
            f"角 x = {degrees:g}°<br>"
            f"cos x = {cos_value:.3f}<br>"
            f"sin x = {sin_value:.3f}<br>"
            f"cos²x + sin²x = {square_sum:.3f}"
        ),
        bgcolor="rgba(255, 255, 255, 0.85)",
        bordercolor="#CBD5E1",
        borderwidth=1,
    )

    figure.update_layout(
        title=f"单位圆：sin²x + cos²x = {square_sum:.3f}",
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
    # 延迟导入：模块顶层保持无 Streamlit 依赖，便于纯函数测试
    import streamlit as st

    degrees = st.slider(
        "角 x（度）",
        min_value=0,
        max_value=360,
        value=int(DEFAULT_DEGREES),
        step=1,
    )
    st.plotly_chart(
        build_unit_circle_figure(float(degrees)), width="stretch"
    )
    st.caption(
        "sin x、cos x 是单位圆上点的纵、横坐标；"
        "拖动角度可见 cos²x + sin²x 恒为 1。"
    )
