"""情境帧渲染：参数滑块 + 纯函数图；异常只提示，不阻断讲解与小测。"""
from __future__ import annotations

from collections.abc import Mapping

import plotly.graph_objects as go

from ..ui.visuals.tangent import build_tangent_figure
from ..ui.visuals.vector_sum import build_vector_sum_figure
from .models import ScenarioSpec


def build_scenario_figure(
    spec: ScenarioSpec, values: Mapping[str, float]
) -> go.Figure:
    """按情境配置与当前参数构造 Plotly 图。"""
    if spec.figure == "tangent_slope":
        return build_tangent_figure(
            lambda x: x**2, x0=float(values["x0"])
        )
    if spec.figure == "vector_sum":
        return build_vector_sum_figure(
            float(values["ax"]),
            float(values["ay"]),
            float(values["bx"]),
            float(values["by"]),
        )
    raise ValueError(f"未知情境图形：{spec.figure}")


def render_scenario(spec: ScenarioSpec) -> str:
    """渲染情境探索区；返回 ok/failed。"""
    try:
        import streamlit as st

        values: dict[str, float] = {}
        for param in spec.params:
            values[param.name] = float(
                st.slider(
                    param.label or param.name,
                    min_value=float(param.minimum),
                    max_value=float(param.maximum),
                    value=float(param.default),
                    step=float(param.step),
                    key=f"scenario_{spec.card_id}_{param.name}",
                )
            )
        st.plotly_chart(
            build_scenario_figure(spec, values),
            width="stretch",
            key=f"scenario_chart_{spec.card_id}",
        )
        for prompt in spec.prompts:
            st.markdown(f"- {prompt}")
        st.caption("情境探索不计入掌握度，也不影响复习调度。")
    except Exception:
        return "failed"
    return "ok"
