"""可选的反馈音效；默认关闭，不依赖外部音频服务。

音频 cue 来自 uisfx（MIT 代码 / CC0 1.0 音频）：
https://github.com/romainsimon/uisfx
commit 9950fe66f993a6660dab9c2651dcbcd899ffd83b
packages/uisfx/sounds/organic/{success,error,complete,select}.mp3

为兼容 PyInstaller 现有打包配置，音频以 base64 常量嵌入，不新增二进制资源。
音量由浏览器原生播放器控制，应用不额外实现音量滑块。
"""
from __future__ import annotations

import base64
import sqlite3
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import streamlit as st

from ..config import db_path
from ..domain.models import Consent
from ..memory.settings_repo import SQLiteSettingsStore

SOUND_ENABLED_KEY = "sound_enabled"
FEEDBACK_ENABLED_KEY = "feedback_sounds_enabled"
PENDING_KEY = "pending_feedback"

CUE_B64 = {
    "correct": (
        "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"
        "B0yQmFH0iIVm3GFB5wqoKiKLFoxHJpt63J2Kqa0MlWbrbB1XXT37EJ6WKn0EBFIkGik7SlYawloP"
        "bGqkQPZZr9L01+p/709DKR2hed1f6ruwzfbNIqpO5q61/WAECbuZsK1xZopMkHiYnUNThSEi700g"
        "mWUR2Z2ET4wtLFmhk8/DMrLS2oh0zBL/+1LE84MMEC8GIesCQacGIISMFJmxMYamyhobBsGSifNo"
        "KeLRLqh8hQyFKzWA0cTHJSfnmkK/Mwx/2KxkrFZ2LtLlgjhwVQXOFVhENDCpIaokdNFxpFIiFj36"
        "KIynt/XVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVUOR1Oj5smlIfhxViS4ZKiSeE4uqmVrBklNTJOqNUAiYScvnWROTRbrDWOTLSMmpNT6"
        "TUSxxv/7UsTsAAw8mweAvKTBbRQglBmMqKQZwkFAqEgKAgEBS37HWhQCqHgIRFSxI8eJB0JWBJ/p"
        "0kjx5p4ZHjB9SEo//rI0kmvngm6MTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//tSxOsABgwTHaCEwGHj"
        "Kd/Y8w1wVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/+1LE1oPNQJzkBhhygAAANIAAAARVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVf/7UsShg8AAAaQAAAAgAAA0gAAABFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//tSxKGDwAABpAAAACAA"
        "ADSAAAAEVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/+1LEoYPAAAGkAAAAIAAANIAAAARVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVQ=="
    ),
    "wrong": (
        "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"
        "VI6n8hLIrk200aGv3hKDkkAGEIdiSXD9UpHJesLQKUu4ASzlz3rWo1Vc7Hglpy/RyVbMzlTVjQwq"
        "wYKAUVMBVwCBrIqJxI88SApHyNZZRqSy2e9wsdOz3JUFZZaf+V13fySL//tSxOUCiYwPCyHBgAHS"
        "rKAJkwzwGCK1QIjUSzx9o5HogkEqHZ4/SFCQ0NCbpfvrmb3+ZMrWwy/7YZGrKClT9lBAgcNekFhd"
        "msWbin6QkLkXVtQaCoo2oWFQy74q3//rFRZMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqr/+1LE4oOJiE8EQLzAQZqa30GDDeiqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqkxBTUUzLjEwMKqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqv/7UsTnAgrIgvYGGE2BMxJX2MAOgKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqTEFNRTMuMTAwqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//tSxKGDwAABpAAAACAA"
        "ADSAAAAEqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqr/+1LEoYPAAAGkAAAAIAAANIAAAASqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqv/7UsShg8AAAaQAAAAgAAA0gAAABKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
    ),
    "complete": (
        "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"
        "wLWnWqq4qUGCkIjTwSaisLEiqrmxR5ncp7mVoQPGuWgrcbancIipSQFZqAjx8w+o0ErWrcHXNgKx"
        "0YreHa6KlAASU3HeLsLnuq6FidNWQE2xYb32YjTTHxYX3w5SpdmfsilAx7Z/L5Nw8TLKvYfYzNt9"
        "+MXIXuf7NTu2Z1SnRMKkrBmVy1JSkZcoxnOtP3pHbpKqZblS0OUcMOdIGvU90IwbhRgQXIkvzAD4"
        "SNMSyv/7UsTtgAwsOQQB5WTBRobhZBw0iAV2egs/FiINJNilCicej6NjcsFQ2jgouCVJG2j8OvNw"
        "2U0ktkKelEeVVNtC40+//+Lum+N/LvWDhR2WvOOxlNxVNFY5PfSpaXLjjZtFPxl6l35v5f5V/jfx"
        "TEFNRTMuMTAwqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqgBCx1A3"
        "lrFSxxdRtzUau6/xpCRDJUojzyQlhk6URsbnq7qcNjJVZJeG+KypY4vC//tSxPIDjh2RAAygbMkg"
        "BqEIJ6DAbTBQQJSHZ/9ymVUO3RVT///6Kv6Kqf//JrJf9lkqH/ZLDI1ls/ZWBg0D0WFxUz///9Yp"
        "qFpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqr/+1LE84MNJZUAZ6RpQXuN3sRkmOGqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqkxBTUUzLjEwMKqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqv/7UsTTg8x5frYkiHzAAAA0gAAABKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqTEFNRTMuMTAwqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//tSxKGDwAABpAAAACAA"
        "ADSAAAAEqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqr/+1LEoYPAAAGkAAAAIAAANIAAAASqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
        "qqqqqg=="
    ),
    "click": (
        "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"
        "huEEHJSYvQDUku2GvKgWsyp87/lmvne1QGU3RUWT63XgwAAEgkJ1K1r1FRR+PJaGbR6NDP9nFf/s"
        "AX+M1//Uhgz//Z9r0sGIYNVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/+1LEtAJIQB0IoOTEQQgD4MAnmMBVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVf/7UsTQAAhMWwRAvGRApIAf9BCMBFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//tSxKGDwAABpAAAACAA"
        "ADSAAAAEVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVU="
    ),
}


@dataclass(frozen=True)
class SoundSettings:
    """声音设置；总开关默认关闭，音量由浏览器播放器控制。"""

    enabled: bool = False
    feedback_enabled: bool = True


def _is_guest(consent: Consent) -> bool:
    """记忆与错题本都关闭时视为游客。"""
    return not (consent.memory or consent.mistake_book)


def load_sound_settings(
    consent: Consent, path: Path | None = None
) -> SoundSettings:
    """读取声音设置；游客用会话状态，持久模式读 settings 表。"""
    if _is_guest(consent):
        return SoundSettings(
            enabled=bool(
                st.session_state.get(SOUND_ENABLED_KEY, False)
            ),
            feedback_enabled=bool(
                st.session_state.get(FEEDBACK_ENABLED_KEY, True)
            ),
        )
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            values = store.get_all()
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return SoundSettings()
    return SoundSettings(
        enabled=bool(values.get(SOUND_ENABLED_KEY, False)),
        feedback_enabled=bool(values.get(FEEDBACK_ENABLED_KEY, True)),
    )


def save_sound_settings(
    consent: Consent,
    *,
    enabled: bool,
    feedback_enabled: bool,
    path: Path | None = None,
) -> bool:
    """保存声音设置；失败时返回 False，不阻断主流程。"""
    values = {
        SOUND_ENABLED_KEY: bool(enabled),
        FEEDBACK_ENABLED_KEY: bool(feedback_enabled),
    }
    if _is_guest(consent):
        st.session_state.update(values)
        return True
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            store.set_many(values)
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    st.session_state.update(values)
    return True


@cache
def cue_bytes(kind: str) -> bytes:
    """解码并缓存内嵌音频 cue；未知 cue 返回空字节。"""
    encoded = CUE_B64.get(kind)
    if not encoded:
        return b""
    return base64.b64decode(encoded)


def cue_html(kind: str) -> str:
    """返回隐藏的 HTML5 audio 元素；仅使用白名单 cue。"""
    encoded = CUE_B64.get(kind)
    if not encoded:
        return ""
    return (
        '<audio autoplay="autoplay" preload="auto" '
        'style="display:none" '
        f'src="data:audio/mpeg;base64,{encoded}"></audio>'
    )


def queue_feedback(kind: str, consent: Consent) -> None:
    """在声音开启时登记一次反馈音，等下一次渲染播放。"""
    if kind not in CUE_B64:
        return
    settings = load_sound_settings(consent)
    if not settings.enabled or not settings.feedback_enabled:
        return
    st.session_state[PENDING_KEY] = kind


def play_pending_feedback(consent: Consent) -> None:
    """播放并清除待播放反馈音；关闭声音时不渲染任何音频。"""
    kind = st.session_state.pop(PENDING_KEY, None)
    if kind is None:
        return
    settings = load_sound_settings(consent)
    if not settings.enabled or not settings.feedback_enabled:
        return
    html = cue_html(kind)
    if html:
        st.markdown(html, unsafe_allow_html=True)
