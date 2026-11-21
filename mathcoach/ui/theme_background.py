"""可选的常量 CSS 背景主题。

CSS 图案改编自 Pattern Craft（MIT，Copyright (c) 2025 Megh Bari）：
https://github.com/megh-bari/pattern-craft
仅使用常量字符串，不加载外部图片，也不拼接用户输入。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st

from ..config import db_path
from ..domain.models import Consent
from ..memory.settings_repo import SQLiteSettingsStore

BACKGROUND_KEY = "background_theme"
BACKGROUND_OPTIONS = {
    "none": "无背景",
    "paper": "纸张纹理",
    "dots": "点阵网格",
    "diagonal": "对角细线",
}

_BACKGROUND_CSS = {
    "paper": {
        "light": """
.stApp, [data-testid="stAppViewContainer"] {
  background-color: #faf9f6 !important;
  background-image:
    radial-gradient(circle at 1px 1px, rgba(0,0,0,0.05) 1px, transparent 0),
    repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.015) 2px, rgba(0,0,0,0.015) 4px),
    repeating-linear-gradient(90deg, transparent, transparent 2px, rgba(0,0,0,0.015) 2px, rgba(0,0,0,0.015) 4px) !important;
  background-size: 8px 8px, 32px 32px, 32px 32px !important;
}
""",
        "dark": """
.stApp, [data-testid="stAppViewContainer"] {
  background-color: #111827 !important;
  background-image:
    radial-gradient(circle at 1px 1px, rgba(255,255,255,0.035) 1px, transparent 0),
    repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.012) 2px, rgba(255,255,255,0.012) 4px),
    repeating-linear-gradient(90deg, transparent, transparent 2px, rgba(255,255,255,0.012) 2px, rgba(255,255,255,0.012) 4px) !important;
  background-size: 8px 8px, 32px 32px, 32px 32px !important;
}
""",
    },
    "dots": {
        "light": """
.stApp, [data-testid="stAppViewContainer"] {
  background-color: #ffffff !important;
  background-image:
    linear-gradient(to right, rgba(0,0,0,0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,0.04) 1px, transparent 1px),
    radial-gradient(circle, rgba(51,65,85,0.10) 1px, transparent 1px) !important;
  background-size: 20px 20px, 20px 20px, 20px 20px !important;
}
""",
        "dark": """
.stApp, [data-testid="stAppViewContainer"] {
  background-color: #0b0b0c !important;
  background-image:
    linear-gradient(to right, rgba(255,255,255,0.05) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255,255,255,0.05) 1px, transparent 1px),
    radial-gradient(circle, rgba(255,255,255,0.08) 1px, transparent 1px) !important;
  background-size: 20px 20px, 20px 20px, 20px 20px !important;
}
""",
    },
    "diagonal": {
        "light": """
.stApp, [data-testid="stAppViewContainer"] {
  background-color: #fafafa !important;
  background-image:
    repeating-linear-gradient(45deg, rgba(0,0,0,0.05) 0, rgba(0,0,0,0.05) 1px, transparent 1px, transparent 20px),
    repeating-linear-gradient(-45deg, rgba(0,0,0,0.05) 0, rgba(0,0,0,0.05) 1px, transparent 1px, transparent 20px) !important;
  background-size: 40px 40px !important;
}
""",
        "dark": """
.stApp, [data-testid="stAppViewContainer"] {
  background-color: #0f172a !important;
  background-image:
    repeating-linear-gradient(45deg, rgba(255,255,255,0.05) 0, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 20px),
    repeating-linear-gradient(-45deg, rgba(255,255,255,0.05) 0, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 20px) !important;
  background-size: 40px 40px !important;
}
""",
    },
}


def _is_guest(consent: Consent) -> bool:
    return not (consent.memory or consent.mistake_book)


def background_css(choice: str, theme: str = "light") -> str:
    """返回白名单背景的常量 CSS；无背景或未知值返回空字符串。"""
    variants = _BACKGROUND_CSS.get(choice)
    if not variants:
        return ""
    return variants["dark" if theme == "dark" else "light"]


def load_background(
    consent: Consent, path: Path | None = None
) -> str:
    """读取背景选择；游客用会话状态，持久模式读 settings 表。"""
    if _is_guest(consent):
        value = st.session_state.get(BACKGROUND_KEY, "none")
    else:
        try:
            store = SQLiteSettingsStore(path or db_path())
            try:
                value = store.get_all().get(BACKGROUND_KEY, "none")
            finally:
                store.close()
        except (OSError, sqlite3.Error):
            value = "none"
    if not isinstance(value, str) or value not in BACKGROUND_OPTIONS:
        return "none"
    return value


def save_background(
    consent: Consent, choice: str, path: Path | None = None
) -> bool:
    """保存白名单背景选择；成功返回 True，失败不阻断主流程。"""
    if choice not in BACKGROUND_OPTIONS:
        return False
    if _is_guest(consent):
        st.session_state[BACKGROUND_KEY] = choice
        return True
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            store.set_many({BACKGROUND_KEY: choice})
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    st.session_state[BACKGROUND_KEY] = choice
    return True


def inject_background_css(consent: Consent) -> None:
    """注入已选背景的常量 CSS；默认无背景时不注入。"""
    choice = load_background(consent)
    if choice == "none":
        return
    try:
        actual_theme = st.get_option("theme.base")
    except Exception:  # noqa: BLE001 - 配置读取失败时回退到浅色
        actual_theme = "light"
    css = background_css(
        choice, "dark" if actual_theme == "dark" else "light"
    )
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
