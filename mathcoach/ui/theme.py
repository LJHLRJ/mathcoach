"""集中管理主题常量 CSS 与布局密度。

仅注入常量字符串，不拼接用户输入；不加载外部字体或图片。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st

from ..config import db_path
from ..domain.models import Consent
from ..memory.settings_repo import SQLiteSettingsStore
from .components import DANGER_CSS

LAYOUT_DENSITY_KEY = "layout_density"
DENSITY_COMFORTABLE = "comfortable"
DENSITY_COMPACT = "compact"
DENSITY_OPTIONS = {
    DENSITY_COMFORTABLE: "宽松",
    DENSITY_COMPACT: "紧凑",
}

# 局部补充：内容区宽度、卡片阴影、主按钮 hover。
# 不重写 Streamlit 组件，所有颜色与间距均为常量。
THEME_CSS = """
<style>
[data-testid="stMarkdown"]:has(style) {
  display: none !important;
}
[data-testid="stMainBlockContainer"] {
  max-width: 920px;
}
[class*="st-key-mc-card-"]:is([data-testid="stVerticalBlock"]),
[class*="st-key-mc-card-"] > [data-testid="stVerticalBlock"] {
  border-color: rgba(38, 39, 48, 0.10) !important;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045);
}
button[kind="primary"],
button[kind="primaryFormSubmit"] {
  transition: transform .12s ease, box-shadow .12s ease;
}
button[kind="primary"]:hover,
button[kind="primaryFormSubmit"]:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(79, 139, 249, 0.18);
}
@media (prefers-reduced-motion: reduce) {
  button {
    transition: none !important;
    transform: none !important;
  }
}
</style>
"""

COMPACT_DENSITY_CSS = """
<style>
[data-testid="stVerticalBlock"] {
  gap: .65rem;
}
</style>
"""


def _is_guest(consent: Consent | None) -> bool:
    return consent is None or not (consent.memory or consent.mistake_book)


def load_layout_density(
    consent: Consent | None, path: Path | None = None
) -> str:
    """读取布局密度；默认宽松，未知值回退宽松。"""
    if _is_guest(consent):
        value = st.session_state.get(
            LAYOUT_DENSITY_KEY, DENSITY_COMFORTABLE
        )
    else:
        try:
            store = SQLiteSettingsStore(path or db_path())
            try:
                values = store.get_all()
            finally:
                store.close()
        except (OSError, sqlite3.Error):
            return DENSITY_COMFORTABLE
        value = values.get(LAYOUT_DENSITY_KEY, DENSITY_COMFORTABLE)
    if not isinstance(value, str) or value not in DENSITY_OPTIONS:
        return DENSITY_COMFORTABLE
    return value


def save_layout_density(
    consent: Consent | None,
    value: str,
    path: Path | None = None,
) -> bool:
    """保存布局密度；失败时不阻断主流程。"""
    if value not in DENSITY_OPTIONS:
        return False
    if _is_guest(consent):
        st.session_state[LAYOUT_DENSITY_KEY] = value
        return True
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            store.set_many({LAYOUT_DENSITY_KEY: value})
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    st.session_state[LAYOUT_DENSITY_KEY] = value
    return True


def layout_density(consent: Consent | None = None) -> str:
    """返回当前会话密度；首次读取后缓存到 session_state。"""
    value = st.session_state.get(LAYOUT_DENSITY_KEY)
    if isinstance(value, str) and value in DENSITY_OPTIONS:
        return value
    value = load_layout_density(consent)
    st.session_state[LAYOUT_DENSITY_KEY] = value
    return value


def density_css(value: str) -> str:
    """返回密度对应的常量 CSS；宽松模式不注入。"""
    return COMPACT_DENSITY_CSS if value == DENSITY_COMPACT else ""


def inject_theme(consent: Consent | None = None) -> None:
    """注入主题与按钮常量 CSS；重复调用不会改变视觉结果。"""
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown(DANGER_CSS, unsafe_allow_html=True)
    css = density_css(layout_density(consent))
    if css:
        st.markdown(css, unsafe_allow_html=True)
