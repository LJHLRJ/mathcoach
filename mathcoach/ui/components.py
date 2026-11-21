"""按钮语义与加载占位常量。

页面通过 button_kwargs() 复用按钮层级，不逐页散落样式；
耗时操作统一使用 loading_skeleton() 占位。
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st

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
