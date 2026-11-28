"""象限符号判定可视化：拖动角度查看象限与 sin/cos 符号。"""
from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

DEFAULT_DEGREES = 120.0
CIRCLE_POINTS = 180
AXIS_LIMIT = 1.35
_EPSILON = 1e-9
_QUADRANT_LABELS = (
    (0.58, 0.58, "I\nsin+ cos+", "#EFF6FF"),
    (-0.58, 0.58, "II\nsin+ cos−", "#FEF2F2"),
    (-0.58, -0.58, "III\nsin− cos−", "#F5F3FF"),
    (0.58, -0.58, "IV\nsin− cos+", "#ECFDF5"),
)


def _clean(value: float) -> float:
    """把浮点噪声归零，避免 180° 时出现 6e-17。"""
    return 0.0 if abs(value) < _EPSILON else value


def _sign(value: float) -> str:
    """返回符号文本；零单独处理。"""
    if abs(value) < _EPSILON:
        return "0"
    return "+" if value > 0 else "−"


def _value_text(value: float) -> str:
    """把函数值写成带符号的三位小数。"""
    sign = _sign(value)
    if sign == "0":
        return "0.000"
    return f"{sign}{abs(value):.3f}"


def quadrant_name(degrees: float) -> str:
    """返回角度所在象限；轴线角返回“坐标轴上”。"""
    value = degrees % 360.0
    if any(
        abs(value - axis) < _EPSILON
        for axis in (0.0, 90.0, 180.0, 270.0, 360.0)
    ):
        return "坐标轴上"
    if value < 90.0:
        return "第一象限"
    if value < 180.0:
        return "第二象限"
    if value < 270.0:
        return "第三象限"
    return "第四象限"


def build_quadrant_sign_figure(
    degrees: float = DEFAULT_DEGREES,
    *,
    circle_points: int = CIRCLE_POINTS,
) -> go.Figure:
    """构造象限符号图。

    Args:
        degrees: 从 x 轴正方向逆时针旋转的角度（度）。
        circle_points: 单位圆采样点数。

    Returns:
        含四象限底色、单位圆、投影与符号标注的 Plotly 图。
    """
    angle = degrees % 360.0
    radians = math.radians(angle)
    cos_value = _clean(math.cos(radians))
    sin_value = _clean(math.sin(radians))
    quadrant = quadrant_name(angle)

    angles = np.linspace(0.0, 2.0 * math.pi, circle_points)
    arc_angles = np.linspace(
        0.0, radians, max(2, circle_points // 4)
    )

    figure = go.Figure()
    for x_pos, y_pos, label, color in _QUADRANT_LABELS:
        figure.add_shape(
            type="rect",
            x0=0.0 if x_pos > 0 else -1.0,
            x1=1.0 if x_pos > 0 else 0.0,
            y0=0.0 if y_pos > 0 else -1.0,
            y1=1.0 if y_pos > 0 else 0.0,
            fillcolor=color,
            line_width=0,
            layer="below",
            opacity=0.65,
        )
        figure.add_annotation(
            x=x_pos,
            y=y_pos,
            text=label,
            showarrow=False,
            font={"size": 11, "color": "#475569"},
            align="center",
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
            x=0.28 * np.cos(arc_angles),
            y=0.28 * np.sin(arc_angles),
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
            f"角 x = {angle:g}°<br>"
            f"所在象限：{quadrant}<br>"
            f"sin x = {_value_text(sin_value)}<br>"
            f"cos x = {_value_text(cos_value)}"
        ),
        bgcolor="rgba(255, 255, 255, 0.88)",
        bordercolor="#CBD5E1",
        borderwidth=1,
    )

    figure.update_layout(
        title=f"象限符号判定：{quadrant}",
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
    """渲染可交互的象限符号图。"""
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
        build_quadrant_sign_figure(float(degrees)), width="stretch"
    )
    st.caption(
        "先用平方关系求绝对值，再由终边所在象限决定正负；"
        "轴线角要单独判断。"
    )
