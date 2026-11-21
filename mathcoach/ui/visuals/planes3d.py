"""3D 平面可视化：三个平面方程 -> 三个 Surface；交点用 numpy 求解。"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

Plane = tuple[float, float, float, float]
DEFAULT_RANGE = (-5.0, 5.0)
DEFAULT_POINTS = 40


def solve_intersection(equations: list[Plane]) -> tuple[float, float, float] | None:
    """解 Ax=b；矩阵奇异（平行/重合/无唯一交点）时返回 None。"""
    matrix = np.array([equation[:3] for equation in equations], dtype=float)
    values = np.array([equation[3] for equation in equations], dtype=float)
    try:
        return tuple(float(value) for value in np.linalg.solve(matrix, values))
    except np.linalg.LinAlgError:
        # 无唯一交点也是合法教学状态，不能阻断渲染
        return None


def build_planes_figure(
    equations: list[Plane],
    x_range: tuple[float, float] = DEFAULT_RANGE,
    y_range: tuple[float, float] = DEFAULT_RANGE,
    points: int = DEFAULT_POINTS,
) -> go.Figure:
    if len(equations) != 3:
        raise ValueError("首期只支持三个平面方程")

    xs = np.linspace(x_range[0], x_range[1], points)
    ys = np.linspace(y_range[0], y_range[1], points)
    grid_x, grid_y = np.meshgrid(xs, ys)
    figure = go.Figure()
    for index, (a, b, c, d) in enumerate(equations, start=1):
        if abs(c) < 1e-9:
            # 竖直平面无法写成 z=...，用 z=0 占位仅用于展示
            grid_z = np.zeros_like(grid_x)
        else:
            grid_z = (d - a * grid_x - b * grid_y) / c
        figure.add_trace(
            go.Surface(
                x=grid_x,
                y=grid_y,
                z=grid_z,
                name=f"平面 {index}",
                showscale=False,
                opacity=0.65,
            )
        )

    point = solve_intersection(equations)
    title = (
        f"三平面交点：({point[0]:.2f}, {point[1]:.2f}, {point[2]:.2f})"
        if point is not None
        else "三平面无唯一交点"
    )
    figure.update_layout(
        title=title,
        scene={
            "xaxis_title": "x",
            "yaxis_title": "y",
            "zaxis_title": "z",
            "aspectmode": "cube",
        },
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return figure


def render() -> None:
    # 延迟导入：模块顶层保持无 Streamlit 依赖，便于纯函数测试
    import streamlit as st

    equations: list[Plane] = [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1)]
    st.plotly_chart(build_planes_figure(equations), width="stretch")
