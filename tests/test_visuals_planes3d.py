"""3D 平面可视化：三个方程三个 Surface；无唯一交点仍返回 Figure。"""
import numpy as np
import pytest

from mathcoach.ui.visuals.planes3d import build_planes_figure, solve_intersection

UNIQUE = [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1)]
PARALLEL = [(1, 1, 1, 1), (1, 1, 1, 2), (1, -1, 0, 0)]


def test_three_planes_create_three_surfaces():
    """三个平面方程生成三个 Surface 轨迹。"""
    figure = build_planes_figure(UNIQUE)

    assert len(figure.data) == 3
    assert all(trace.type == "surface" for trace in figure.data)


def test_intersection_is_solved():
    """三个独立平面求解出唯一交点。"""
    point = solve_intersection(UNIQUE)

    assert point == pytest.approx((1.0, 1.0, 1.0))


def test_vertical_planes_keep_constant_coordinate():
    """垂直平面的网格坐标保持常量。"""
    figure = build_planes_figure(UNIQUE)

    assert np.allclose(np.asarray(figure.data[0].x, dtype=float), 1.0)
    assert np.allclose(np.asarray(figure.data[1].y, dtype=float), 1.0)


def test_no_intersection_returns_none_point_and_figure():
    """无唯一交点时返回 None，figure 仍可正常生成。"""
    assert solve_intersection(PARALLEL) is None

    figure = build_planes_figure(PARALLEL)

    assert len(figure.data) == 3
    assert all(trace.type == "surface" for trace in figure.data)
