"""设置页：数据与隐私、导出、清除与基础调度设置。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from ..config import db_path
from ..domain.models import Consent
from ..domain.settings import (
    AppSettings,
    export_json,
    export_markdown,
    export_mistakes_csv,
    export_receipts_csv,
)
from ..llm import OfflineProvider
from ..memory.repository import Repository
from ..memory.settings_repo import SQLiteSettingsStore
from .icons import ICON_CHECK, ICON_ERROR, ICON_INFO


def _is_guest(consent: Consent) -> bool:
    return not (consent.memory or consent.mistake_book)


@st.cache_data(show_spinner=False)
def load_settings(path: str) -> dict[str, Any]:
    """读取指定数据库的 settings 表；保存后由调用方清除缓存。"""
    store = SQLiteSettingsStore(path)
    try:
        return store.get_all()
    finally:
        store.close()


def current_settings(consent: Consent) -> AppSettings:
    """返回当前会话生效的设置；游客模式读取会话内存。"""
    if _is_guest(consent):
        mapping = st.session_state.get("guest_settings", {})
    else:
        mapping = load_settings(str(db_path()))
    return AppSettings.from_mapping(mapping)


def _save_settings(consent: Consent, settings: AppSettings) -> None:
    if _is_guest(consent):
        st.session_state["guest_settings"] = settings.to_mapping()
        return
    store = SQLiteSettingsStore(db_path())
    try:
        store.set_many(settings.to_mapping())
    finally:
        store.close()
    load_settings.clear()


def _render_notices() -> None:
    if st.session_state.pop("settings_saved", False):
        st.success("设置已保存。")
    cleared = st.session_state.pop("settings_cleared", None)
    if cleared is not None:
        st.success(f"学习数据已清除，共删除 {cleared} 条记录。")


def _render_export(repository: Repository, consent: Consent) -> None:
    st.divider()
    st.markdown("### 导出学习数据")
    if _is_guest(consent):
        st.info(f"{ICON_INFO} 游客模式没有持久学习数据可导出。")
        return

    receipts = repository.list_receipts(limit=None)
    mistakes = repository.list_mistakes(limit=None)
    review_items = repository.list_review_items()
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    settings = current_settings(consent)
    st.caption("导出不包含 API 密钥、secrets 文件或审计日志。")
    st.download_button(
        "下载完整 JSON",
        data=export_json(
            receipts=receipts,
            mistakes=mistakes,
            review_items=review_items,
            settings=settings,
            now=now,
        ),
        file_name=f"mathcoach-{stamp}.json",
        mime="application/json",
        key="settings_export_json",
    )
    left, right = st.columns(2)
    with left:
        st.download_button(
            "下载收据 CSV",
            data=export_receipts_csv(receipts),
            file_name=f"mathcoach-receipts-{stamp}.csv",
            mime="text/csv",
            key="settings_export_receipts",
        )
    with right:
        st.download_button(
            "下载错题 CSV",
            data=export_mistakes_csv(mistakes),
            file_name=f"mathcoach-mistakes-{stamp}.csv",
            mime="text/csv",
            key="settings_export_mistakes",
        )
    st.download_button(
        "下载 Markdown 报告",
        data=export_markdown(
            receipts=receipts,
            mistakes=mistakes,
            settings=settings,
            now=now,
        ),
        file_name=f"mathcoach-report-{stamp}.md",
        mime="text/markdown",
        key="settings_export_markdown",
    )


def _render_clear(repository: Repository, consent: Consent) -> None:
    st.divider()
    st.markdown("### 清除全部学习数据")
    if _is_guest(consent):
        st.info(f"{ICON_INFO} 游客模式没有持久数据，无需清除。")
        return

    st.caption(
        "范围：收据、错题本、复习队列、每日挑战、挑战赛、掌握概率。"
        "设置与审计日志默认保留。"
    )
    with st.form("settings_clear_form"):
        confirmation = st.text_input(
            "输入 DELETE 确认", key="settings_clear_confirm"
        )
        purge_audit = st.checkbox(
            "同时删除安全审计日志", key="settings_clear_audit"
        )
        submitted = st.form_submit_button("永久清除学习数据")
    if not submitted:
        return
    if confirmation != "DELETE":
        st.error(f"{ICON_ERROR} 未执行：请输入 DELETE。")
        return
    store = SQLiteSettingsStore(db_path())
    try:
        counts = store.clear_learning_data(keep_audit=not purge_audit)
    finally:
        store.close()
    repository.record_audit("settings_clear", "ok")
    st.session_state["settings_cleared"] = sum(counts.values())
    st.rerun()


def render_settings_page(
    repository: Repository, consent: Consent, provider
) -> None:
    """渲染设置 Tab：状态、基础设置、导出与数据清除。"""
    st.subheader("设置")
    _render_notices()
    if _is_guest(consent):
        st.warning("游客模式：设置与学习数据仅保存在当前会话，关闭后不保留。")
        st.caption("存储：游客内存（进程结束即丢弃）")
    else:
        st.caption(f"存储：本地 SQLite · {db_path()}")

    settings = current_settings(consent)
    offline = isinstance(provider, OfflineProvider) or getattr(
        provider, "degraded", False
    )
    if offline:
        st.info(f"{ICON_INFO} 当前模式：离线模板")
    else:
        st.success(f"{ICON_CHECK} 当前模式：AI")

    st.markdown("### 基础设置")
    with st.form("settings_general_form"):
        ai_enabled = st.toggle(
            "启用 AI 模式",
            value=settings.ai_enabled,
            key="settings_ai_enabled",
        )
        daily_limit = st.number_input(
            "每日复习上限（0 = 不限制）",
            min_value=0,
            max_value=999,
            value=settings.daily_review_limit,
            step=1,
            key="settings_daily_limit",
        )
        saved = st.form_submit_button("保存设置")
    if saved:
        new_settings = AppSettings(
            ai_enabled=ai_enabled,
            daily_review_limit=int(daily_limit),
        )
        _save_settings(consent, new_settings)
        repository.record_audit("settings_save", "ok")
        st.session_state["settings_saved"] = True
        st.rerun()

    if offline and settings.ai_enabled:
        st.warning(
            "已启用 AI 模式，但当前未检测到可用 API Key；"
            "仍使用离线模板。密钥配置将在后续批次提供。"
        )
    elif offline:
        st.caption("未配置 API Key 时使用离线模板，判分逻辑不变。")

    _render_export(repository, consent)
    _render_clear(repository, consent)
