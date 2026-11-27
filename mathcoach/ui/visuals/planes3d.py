"""3D 平面可视化：三个平面方程 -> 三个 Surface；交点用 numpy 求解。"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

Plane = tuple[float, float, float, float]
DEFAULT_RANGE = (-5.0, 5.0)
DEFAULT_POINTS = 40


def _plane_grid(
    a: float,
    b: float,
    c: float,
    d: float,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    z_range: tuple[float, float],
    points: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """按平面法向选择参数化网格，竖直平面不退回 z=0。

    ``c`` 非零时用 x/y 网格求 z；否则用 y/z 或 x/z 网格求常值坐标，
    保证 x=const、y=const 的平面仍画在正确位置。

    Args:
        a: x 系数。
        b: y 系数。
        c: z 系数。
        d: 常数项。
        x_range: x 取值范围。
        y_range: y 取值范围。
        z_range: z 取值范围，仅竖直平面使用。
        points: 每个轴的采样点数。

    Returns:
        三个二维数组 ``(x, y, z)``，可直接传给 Plotly Surface。

    Raises:
        ValueError: 三个系数都为 0，方程退化，无法渲染。
    """
    if abs(c) >= 1e-9:
        xs = np.linspace(x_range[0], x_range[1], points)
        ys = np.linspace(y_range[0], y_range[1], points)
        grid_x, grid_y = np.meshgrid(xs, ys)
        return grid_x, grid_y, (d - a * grid_x - b * grid_y) / c
    if abs(a) >= 1e-9:
        ys = np.linspace(y_range[0], y_range[1], points)
        zs = np.linspace(z_range[0], z_range[1], points)
        grid_y, grid_z = np.meshgrid(ys, zs)
        return (d - b * grid_y) / a, grid_y, grid_z
    if abs(b) >= 1e-9:
        xs = np.linspace(x_range[0], x_range[1], points)
        zs = np.linspace(z_range[0], z_range[1], points)
        grid_x, grid_z = np.meshgrid(xs, zs)
        return grid_x, np.full_like(grid_x, d / b), grid_z
    raise ValueError("平面方程三个系数都为 0，无法渲染")


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
    z_range: tuple[float, float] = DEFAULT_RANGE,
) -> go.Figure:
    if len(equations) != 3:
        raise ValueError("首期只支持三个平面方程")

    figure = go.Figure()
    for index, (a, b, c, d) in enumerate(equations, start=1):
        grid_x, grid_y, grid_z = _plane_grid(
            a, b, c, d, x_range, y_range, z_range, points
        )
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
