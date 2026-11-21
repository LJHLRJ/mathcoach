"""切线可视化：曲线与切线两条 trace；只渲染，不参与判定。"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import plotly.graph_objects as go

DEFAULT_X_RANGE = (-3.0, 3.0)
DEFAULT_POINTS = 200
DERIVATIVE_STEP = 1e-5


def _numeric_derivative(func: Callable[[float], float], x0: float) -> float:
    """中心差分；不依赖符号计算，也不调用 LLM。"""
    return (func(x0 + DERIVATIVE_STEP) - func(x0 - DERIVATIVE_STEP)) / (
        2 * DERIVATIVE_STEP
    )


def build_tangent_figure(
    func: Callable[[float], float],
    x0: float = 1.0,
    x_range: tuple[float, float] = DEFAULT_X_RANGE,
    points: int = DEFAULT_POINTS,
) -> go.Figure:
    xs = np.linspace(x_range[0], x_range[1], points)
    ys = np.array([float(func(float(x))) for x in xs])
    slope = _numeric_derivative(func, x0)
    tangent_ys = float(func(x0)) + slope * (xs - x0)

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(x=xs, y=ys, mode="lines", name="曲线")
    )
    figure.add_trace(
        go.Scatter(x=xs, y=tangent_ys, mode="lines", name="切线")
    )
    figure.update_layout(
        title=f"f(x) 在 x={x0:g} 处的切线（斜率 {slope:.3f}）",
        xaxis_title="x",
        yaxis_title="y",
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    return figure


def render() -> None:
    # 延迟导入：模块顶层保持无 Streamlit 依赖，便于纯函数测试
    import streamlit as st

    st.plotly_chart(build_tangent_figure(lambda x: x**2, x0=1.0), width="stretch")
