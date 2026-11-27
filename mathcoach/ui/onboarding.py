"""首次使用后的非阻塞引导：错题本、复习队列与设置入口。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st

from ..config import db_path
from ..domain.models import Consent
from ..memory.repository import Repository
from ..memory.settings_repo import SQLiteSettingsStore
from .icons import ICON_CHECK, ICON_INFO

ONBOARDING_KEY = "onboarding_seen"
SESSION_COMPLETED = "onboarding_first_use_done"
SESSION_DISMISSED = "onboarding_dismissed"


def _is_guest(consent: Consent) -> bool:
    """记忆与错题本都关闭时视为游客。"""
    return not (consent.memory or consent.mistake_book)


def mark_first_use_done() -> None:
    """标记当前会话已完成第一道题或第一次复习。"""
    st.session_state[SESSION_COMPLETED] = True


def first_use_completed() -> bool:
    """当前会话是否已完成首次使用。"""
    return bool(st.session_state.get(SESSION_COMPLETED))


def repository_has_history(repository: Repository) -> bool:
    """是否存在既往收据或错题；用于避免升级后打扰已有学习记录的人。"""
    return bool(
        repository.list_receipts(limit=1)
        or repository.list_mistakes(limit=1)
    )


def should_render_onboarding(
    *, completed: bool, had_history: bool, dismissed: bool
) -> bool:
    """仅在完成首次使用、无既往记录且未关闭时展示引导。"""
    return completed and not had_history and not dismissed


def onboarding_dismissed(
    consent: Consent, path: Path | None = None
) -> bool:
    """读取引导已读状态；游客使用会话状态，持久模式读 settings 表。"""
    if st.session_state.get(SESSION_DISMISSED):
        return True
    if _is_guest(consent):
        return False
    target = path or db_path()
    try:
        store = SQLiteSettingsStore(target)
        try:
            return bool(store.get_all().get(ONBOARDING_KEY))
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        # 引导不是核心流程；读取失败时按未读处理，下次再试
        return False


def dismiss_onboarding(consent: Consent, path: Path | None = None) -> None:
    """关闭引导并记录已读；持久化失败时保持会话内不再出现。"""
    st.session_state[SESSION_DISMISSED] = True
    if _is_guest(consent):
        return
    target = path or db_path()
    try:
        store = SQLiteSettingsStore(target)
        try:
            store.set_many({ONBOARDING_KEY: True})
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return


def render_onboarding(consent: Consent, *, had_history: bool) -> None:
    """渲染非阻塞引导卡片；不调用 st.stop，不拦截页签导航。"""
    completed = first_use_completed()
    if not completed or had_history:
        return
    if not should_render_onboarding(
        completed=completed,
        had_history=had_history,
        dismissed=onboarding_dismissed(consent),
    ):
        return
    with st.container(border=True):
        st.markdown(f"**{ICON_INFO} 新手引导**")
        st.write("你已经完成第一次练习。接下来可以从这三个入口继续：")
        st.markdown(
            "- **错题本**：答错的题会自动收集，可查看错因与变式。\n"
            "- **复习队列**：到期错题会进入复习清单和智能复习包。\n"
            "- **设置**：可调整每日复习上限、复习配比、字号与 AI 配置。"
        )
        left, right = st.columns(2)
        if left.button("知道了", key="onboarding_dismiss", icon=ICON_CHECK):
            dismiss_onboarding(consent)
            st.rerun()
        if right.button("跳过引导", key="onboarding_skip"):
            dismiss_onboarding(consent)
            st.rerun()
