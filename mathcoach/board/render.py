"""板书帧渲染：按图形名分派到纯函数构建器，异常不阻断步骤填写。"""
from __future__ import annotations

import plotly.graph_objects as go

from ..ui.visuals.amplitude_period import build_wave_figure
from ..ui.visuals.cosine_rule import build_cosine_rule_figure
from .models import BoardFrameSpec


def build_frame_figure(frame: BoardFrameSpec) -> go.Figure:
    """按帧配置构造 Plotly 图；未知图形抛 ValueError。"""
    if frame.figure == "wave":
        return build_wave_figure(
            float(frame.params.get("amplitude", 1.0)),
            float(frame.params.get("omega", 1.0)),
        )
    if frame.figure == "cosine_rule":
        return build_cosine_rule_figure(
            float(frame.params.get("a", 3.0)),
            float(frame.params.get("b", 4.0)),
            float(frame.params.get("angle_c", 90.0)),
            highlight=frame.highlight,
        )
    raise ValueError(f"未知板书图形：{frame.figure}")


def render_frame(frame: BoardFrameSpec) -> str:
    """在 Streamlit 中渲染一帧；返回 ok/failed。"""
    try:
        figure = build_frame_figure(frame)
    except Exception:
        return "failed"
    try:
        import streamlit as st

        st.plotly_chart(figure, width="stretch")
    except Exception:
        return "failed"
    return "ok"
