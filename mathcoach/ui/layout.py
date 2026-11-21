"""可复用的 UI 布局封装：只做渲染，不接触业务状态。"""
from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st

# 匹配含 ^ 或 _ 的连续行内公式片段，不跨中文与换行
_MATH_RUN = re.compile(
    r"[A-Za-z0-9\u0370-\u03ff\u2190-\u22ff\\+\-*/=<>^_{}()\[\]|.,'\t ]*"
    r"[\^_]"
    r"[A-Za-z0-9\u0370-\u03ff\u2190-\u22ff\\+\-*/=<>^_{}()\[\]|.,'\t ]*"
)


def math_markdown(text: str) -> str:
    """把含 ^ 或 _ 的行内公式包进 $...$；已有美元符号的文本保持原样。"""
    if "$" in text:
        return text

    def _wrap(match: re.Match[str]) -> str:
        raw = match.group(0)
        core = raw.strip()
        if not core:
            return raw
        leading = raw[: len(raw) - len(raw.lstrip())]
        trailing = raw[len(raw.rstrip()) :]
        return f"{leading}${core}${trailing}"

    return _MATH_RUN.sub(_wrap, text)


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
