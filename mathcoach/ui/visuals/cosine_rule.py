"""余弦定理三角形图：已知两边与夹角，展示第三边与公式。

只渲染，不参与判定；模块顶层不依赖 Streamlit。
"""
from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

DEFAULT_A = 3.0
DEFAULT_B = 4.0
DEFAULT_ANGLE_C = 90.0
MIN_ANGLE_C = 1.0
MAX_ANGLE_C = 179.0
ARC_POINTS = 24
_EPSILON = 1e-9


def _safe_side(value: float, fallback: float) -> float:
    """边长必须为正；非法值回退默认。"""
    return value if value > _EPSILON else fallback


def build_cosine_rule_figure(
    a: float = DEFAULT_A,
    b: float = DEFAULT_B,
    angle_c: float = DEFAULT_ANGLE_C,
    *,
    highlight: str = "",
) -> go.Figure:
    """构造余弦定理三角形图。

    Args:
        a: 角 A 的对边 BC。
        b: 角 B 的对边 CA。
        angle_c: 夹角 C，单位为度；限制在 1–179 度。
        highlight: 高亮元素，``minus`` / ``angle`` / ``side_c`` / 空串。

    Returns:
        含三角形、边角标注与公式说明的 Plotly 图。
    """
    side_a = _safe_side(float(a), DEFAULT_A)
    side_b = _safe_side(float(b), DEFAULT_B)
    angle = min(max(float(angle_c), MIN_ANGLE_C), MAX_ANGLE_C)
    radians = math.radians(angle)
    side_c = math.sqrt(
        side_a**2
        + side_b**2
        - 2.0 * side_a * side_b * math.cos(radians)
    )

    # C 在原点，A 在 x 轴正方向，B 由边长 a 与夹角 C 确定。
    ax, ay = side_b, 0.0
    bx = side_a * math.cos(radians)
    by = side_a * math.sin(radians)

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[0.0, ax, bx, 0.0],
            y=[0.0, ay, by, 0.0],
            mode="lines",
            name="三角形",
            line={"color": "#334155", "width": 3},
            fill="toself",
            fillcolor="rgba(79, 139, 249, 0.08)",
            hoverinfo="skip",
        )
    )
    if highlight == "side_c":
        figure.add_trace(
            go.Scatter(
                x=[ax, bx],
                y=[ay, by],
                mode="lines",
                name="边 c",
                line={"color": "#DC3545", "width": 5},
                hoverinfo="skip",
            )
        )

    arc_radius = min(side_a, side_b) * 0.18
    arc_angles = np.linspace(0.0, radians, ARC_POINTS)
    figure.add_trace(
        go.Scatter(
            x=arc_radius * np.cos(arc_angles),
            y=arc_radius * np.sin(arc_angles),
            mode="lines",
            name="角 C",
            line={
                "color": "#DC3545" if highlight == "angle" else "#7C3AED",
                "width": 3 if highlight == "angle" else 2,
            },
            hoverinfo="skip",
        )
    )

    label_offsets = _label_offsets(side_a, side_b, bx, by)
    for text, x, y in (
        ("A", ax + label_offsets[0], ay + label_offsets[1]),
        ("B", bx + label_offsets[2], by + label_offsets[3]),
        ("C", label_offsets[4], label_offsets[5]),
    ):
        figure.add_annotation(
            x=x,
            y=y,
            text=text,
            showarrow=False,
            font={"size": 15, "color": "#0F172A"},
        )

    for text, x, y in (
        (f"a = {side_a:g}", bx / 2.0, by / 2.0),
        (f"b = {side_b:g}", ax / 2.0, ay / 2.0),
        (f"c = {side_c:.3f}", (ax + bx) / 2.0, (ay + by) / 2.0),
    ):
        figure.add_annotation(
            x=x,
            y=y,
            text=text,
            showarrow=False,
            font={"size": 12, "color": "#475569"},
            bgcolor="rgba(255, 255, 255, 0.85)",
        )

    figure.add_annotation(
        x=0.02,
        y=0.98,
        xref="paper",
        yref="paper",
        xanchor="left",
        yanchor="top",
        align="left",
        showarrow=False,
        text=(
            "c² = a² + b² − 2ab cos C<br>"
            f"a = {side_a:g}，b = {side_b:g}，C = {angle:g}°<br>"
            f"c ≈ {side_c:.3f}"
        ),
        bgcolor="rgba(255, 255, 255, 0.9)",
        bordercolor="#CBD5E1",
        borderwidth=1,
        font={"size": 12, "color": "#0F172A"},
    )
    if highlight == "minus":
        figure.add_annotation(
            x=0.02,
            y=0.72,
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="top",
            showarrow=False,
            text="关注减号项：−2ab cos C",
            font={"size": 12, "color": "#DC3545"},
        )

    limit = max(side_a, side_b, side_c) * 1.25
    figure.update_layout(
        title="余弦定理：c² = a² + b² − 2ab cos C",
        xaxis={"visible": False, "range": [-0.1, limit]},
        yaxis={
            "visible": False,
            "range": [-0.1, limit],
            "scaleanchor": "x",
            "scaleratio": 1.0,
        },
        height=380,
        margin={"l": 30, "r": 30, "t": 50, "b": 20},
        showlegend=False,
        plot_bgcolor="white",
    )
    return figure


def _label_offsets(
    side_a: float, side_b: float, bx: float, by: float
) -> tuple[float, float, float, float, float, float]:
    """按三角形尺度给顶点标签留出偏移。"""
    offset = max(side_a, side_b, 1.0) * 0.06
    return (
        offset,
        -offset,
        offset * 0.6,
        offset * 0.9,
        -offset * 1.4,
        -offset,
    )


def render() -> None:
    """渲染可交互的余弦定理图。"""
    import streamlit as st

    side_a = st.slider(
        "a（BC 边长）", min_value=1.0, max_value=8.0, value=DEFAULT_A, step=0.5
    )
    side_b = st.slider(
        "b（CA 边长）", min_value=1.0, max_value=8.0, value=DEFAULT_B, step=0.5
    )
    angle = st.slider(
        "C（夹角，度）",
        min_value=30.0,
        max_value=150.0,
        value=DEFAULT_ANGLE_C,
        step=5.0,
    )
    st.plotly_chart(
        build_cosine_rule_figure(float(side_a), float(side_b), float(angle)),
        width="stretch",
    )
    st.caption(
        "已知两边及其夹角时用余弦定理求第三边；"
        "夹角为 90° 时减号项消失，退化为勾股定理。"
    )
