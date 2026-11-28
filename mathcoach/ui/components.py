"""按钮语义与加载占位常量。

页面通过 button_kwargs() 复用按钮层级，不逐页散落样式；
耗时操作统一使用 loading_skeleton() 占位。
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st
from streamlit.errors import StreamlitAPIException

try:
    from streamlit.errors import (
        StreamlitInvalidLayoutContextError
        as _InvalidFragmentRerunError,
    )
except ImportError:  # Streamlit 1.59.0 在 scope 错误时抛 StreamlitAPIException
    _InvalidFragmentRerunError = None

PRIMARY = "primary"
SECONDARY = "secondary"
DANGER = "danger"

BUTTON_TYPES = {
    PRIMARY: "primary",
    SECONDARY: "secondary",
    DANGER: "secondary",
}
DANGER_KEY = "settings_clear_submit"

SKELETON_INLINE = 56
SKELETON_CARD = 140
SKELETON_PANEL = 220
SKELETON_HEIGHTS = {
    "inline": SKELETON_INLINE,
    "card": SKELETON_CARD,
    "panel": SKELETON_PANEL,
}

DANGER_CSS = f"""
<style>
.st-key-{DANGER_KEY} button {{
  color: #b42318;
  border-color: rgba(180, 35, 24, .35);
}}
.st-key-{DANGER_KEY} button:hover {{
  color: #912018;
  border-color: rgba(180, 35, 24, .55);
  background-color: rgba(180, 35, 24, .04);
}}
</style>
"""


def button_kwargs(role: str = SECONDARY) -> dict[str, str]:
    """返回 st.button / st.form_submit_button 的 type 参数。"""
    return {"type": BUTTON_TYPES.get(role, "secondary")}


@contextmanager
def loading_skeleton(height: int = SKELETON_INLINE) -> Iterator[None]:
    """固定高度骨架占位；在 with 内执行耗时操作。"""
    with st.skeleton(height=height):
        yield


def is_fragment_rerun_error(exc: Exception) -> bool:
    """判断异常是否表示当前上下文不能做片段级 rerun。"""
    if _InvalidFragmentRerunError is not None and isinstance(
        exc, _InvalidFragmentRerunError
    ):
        return True
    return (
        isinstance(exc, StreamlitAPIException)
        and 'scope="fragment"' in str(exc)
    )


def rerun_fragment() -> None:
    """片段内局部 rerun；旧版 Streamlit 或整页执行时回退全局 rerun。"""
    try:
        st.rerun(scope="fragment")
    except Exception as exc:
        if is_fragment_rerun_error(exc):
            st.rerun()
        raise
