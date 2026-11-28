"""可视化注册表：卡片级与 KC 级组件；未知 ID 返回 None 且不抛异常。"""
from __future__ import annotations

from collections.abc import Callable, Iterable


def _render_tangent() -> None:
    # 延迟导入，避免注册表在没有 Plotly/Streamlit 时被 import 拖垮
    from .tangent import render

    render()


def _render_planes3d() -> None:
    from .planes3d import render

    render()


def _render_unit_circle() -> None:
    from .unit_circle import render

    render()


def _render_quadrant_sign() -> None:
    from .quadrant_sign import render

    render()


def _render_supplement_angle() -> None:
    from .supplement_angle import render

    render()


def _render_amplitude_period() -> None:
    from .amplitude_period import render

    render()


_VISUALS: dict[str, Callable[[], None]] = {
    "hs-func-004": _render_tangent,  # 导数的几何意义：曲线与切线
    "ug-linear-004": _render_planes3d,  # 线性方程组：三平面交点
    "hs-trig-002": _render_unit_circle,  # 同角平方关系：单位圆投影
}

_KC_VISUALS: dict[str, Callable[[], None]] = {
    "kc-hs-trig-002-p1": _render_quadrant_sign,  # 象限符号判定
    "kc-hs-trig-003-f1": _render_supplement_angle,  # 补角公式
    "kc-hs-trig-004-f1": _render_amplitude_period,  # 振幅与周期
}


def get_visual(card_id: str) -> Callable[[], None] | None:
    """按卡片返回可视化组件；未登记返回 None。"""
    return _VISUALS.get(card_id)


def get_kc_visual(kc_id: str) -> Callable[[], None] | None:
    """按 KC 返回动态讲解组件；未登记返回 None。"""
    return _KC_VISUALS.get(kc_id)


def _run(visual: Callable[[], None] | None) -> str:
    """执行组件并返回 none/ok/failed；任何渲染异常都不抛出。"""
    if visual is None:
        return "none"
    try:
        visual()
    except Exception:
        # 可视化是可选增强，任何渲染异常都不应阻断学习流程
        return "failed"
    return "ok"


def render_visual(card_id: str) -> str:
    """渲染卡片级可视化，返回 none/ok/failed。"""
    return _run(get_visual(card_id))


def render_kc_visual(kc_id: str) -> str:
    """渲染 KC 级动态讲解，返回 none/ok/failed。"""
    return _run(get_kc_visual(kc_id))


def kc_visuals_for_exercises(
    exercise_ids: Iterable[str],
) -> tuple[tuple[str, str], ...]:
    """按题目顺序返回去重后的 KC 动态讲解候选。

    只保留已登记组件且目录中存在的 KC；未知题目或 KC 会被跳过。
    """
    from ...tutor.catalog import EXERCISE_KC, KC_BY_ID

    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for exercise_id in exercise_ids:
        for kc_id in EXERCISE_KC.get(exercise_id, ()):
            if kc_id in seen:
                continue
            seen.add(kc_id)
            kc = KC_BY_ID.get(kc_id)
            if kc is None or kc_id not in _KC_VISUALS:
                continue
            result.append((kc_id, kc.name))
    return tuple(result)
