"""专注音频外部入口；不内置曲库，也不在应用内自动播放。"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from ..config import db_path
from ..domain.models import Consent
from ..memory.repository import Repository
from ..memory.settings_repo import SQLiteSettingsStore
from .components import PRIMARY, button_kwargs
from .icons import ICON_ERROR, ICON_INFO

FOCUS_ENABLED_KEY = "focus_audio_enabled"


@dataclass(frozen=True)
class FocusSource:
    """外部专注音频站点；许可证由对应项目负责。"""

    name: str
    url: str
    repository: str
    license_note: str


FOCUS_SOURCES = (
    FocusSource(
        name="Noisekun",
        url="https://noisekun.com",
        repository="https://github.com/mateusfg7/Noisekun",
        license_note="代码 MIT；音源许可证见项目 README",
    ),
    FocusSource(
        name="Moodist",
        url="https://moodist.mvze.net",
        repository="https://github.com/remvze/moodist",
        license_note="代码 MIT；音源为 Pixabay/CC0 等第三方许可",
    ),
    FocusSource(
        name="Open Lo-Fi",
        url="https://github.com/btahir/open-lofi",
        repository="https://github.com/btahir/open-lofi",
        license_note="CC0 1.0",
    ),
)


def _is_guest(consent: Consent) -> bool:
    return not (consent.memory or consent.mistake_book)


def load_focus_enabled(
    consent: Consent, path: Path | None = None
) -> bool:
    """读取专注音频入口开关；默认关闭。"""
    if _is_guest(consent):
        return bool(st.session_state.get(FOCUS_ENABLED_KEY, False))
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            values = store.get_all()
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    return bool(values.get(FOCUS_ENABLED_KEY, False))


def save_focus_enabled(
    consent: Consent, enabled: bool, path: Path | None = None
) -> bool:
    """保存专注音频入口开关；失败时不阻断主流程。"""
    if _is_guest(consent):
        st.session_state[FOCUS_ENABLED_KEY] = bool(enabled)
        return True
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            store.set_many({FOCUS_ENABLED_KEY: bool(enabled)})
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    st.session_state[FOCUS_ENABLED_KEY] = bool(enabled)
    return True


def render_focus_audio(
    repository: Repository, consent: Consent
) -> None:
    """渲染专注音频外部入口；不播放音频、不调节外部音量。"""
    st.markdown("### 专注音频")
    st.caption(
        "仅提供外部入口，不内置曲库。播放、音量和许可证由对应网站负责；"
        "本应用不会自动播放，也无法停止外部页面中的音频。"
    )
    enabled = load_focus_enabled(consent)
    with st.form("settings_focus_audio_form"):
        enabled_new = st.toggle(
            "显示专注音频外部入口",
            value=enabled,
            key="settings_focus_audio_enabled",
        )
        saved = st.form_submit_button(
            "保存专注音频设置", **button_kwargs(PRIMARY)
        )
    if saved:
        if save_focus_enabled(consent, enabled_new):
            repository.record_audit("settings_focus_audio", "ok")
            st.session_state["settings_focus_audio_saved"] = True
            st.rerun()
        else:
            st.error(f"{ICON_ERROR} 专注音频设置保存失败，请重试。")
    if not enabled:
        st.caption(f"{ICON_INFO} 默认关闭；开启后显示外部入口。")
        return
    for source in FOCUS_SOURCES:
        st.link_button(f"打开 {source.name}", source.url)
        st.caption(f"{source.name} · {source.license_note}")
