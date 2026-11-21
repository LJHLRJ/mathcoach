"""可复用的 UI 布局封装：只做渲染，不接触业务状态。"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


@contextmanager
def card(title: str, caption: str = "") -> Iterator[st.delta_generator.DeltaGenerator]:
    """带边框的卡片区块；标题使用语义化 subheader。"""
    with st.container(border=True) as container:
        st.subheader(title)
        if caption:
            st.caption(caption)
        yield container


def kpi_row(items: list[tuple[str, str]]) -> None:
    """把若干 KPI 并排渲染为带边框的 metric。"""
    with st.container(horizontal=True):
        for label, value in items:
            st.metric(label, value, border=True)


def hint_block(level: int, body: str) -> None:
    """提示卡片：层级用 caption 标注，正文用 info 呈现。"""
    with st.container(border=True):
        st.caption(f"提示层级 L{level}")
        st.info(body)
