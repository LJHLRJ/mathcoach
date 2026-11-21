"""可视化注册表：card_id -> 渲染组件；未知卡返回 None。"""
from __future__ import annotations

from collections.abc import Callable


def _render_tangent() -> None:
    # 延迟导入，避免注册表在没有 Plotly/Streamlit 时被 import 拖垮
    from .tangent import render

    render()


def _render_planes3d() -> None:
    from .planes3d import render

    render()


_VISUALS: dict[str, Callable[[], None]] = {
    "hs-func-004": _render_tangent,  # 导数的几何意义：曲线与切线
    "ug-linear-004": _render_planes3d,  # 线性方程组：三平面交点
}


def get_visual(card_id: str) -> Callable[[], None] | None:
    return _VISUALS.get(card_id)


def render_visual(card_id: str) -> str:
    """返回 none/ok/failed，供 UI 决定是否显示“可视化暂不可用”。"""
    visual = get_visual(card_id)
    if visual is None:
        return "none"
    try:
        visual()
    except Exception:
        # 可视化是可选增强，任何渲染异常都不应阻断学习流程
        return "failed"
    return "ok"
