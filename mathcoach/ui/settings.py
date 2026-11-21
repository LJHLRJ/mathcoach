"""设置页：数据与隐私、导出、清除与基础调度设置。"""
from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from datetime import time as dt_time
from typing import Any

import streamlit as st

from ..config import content_strict, db_path
from ..domain.fsrs import DEFAULT_PARAMS
from ..domain.models import Consent
from ..domain.settings import (
    AppSettings,
    export_audit_csv,
    export_audit_json,
    export_json,
    export_markdown,
    export_mistakes_csv,
    export_receipts_csv,
)
from ..llm import (
    OfflineProvider,
    OpenAICompatibleProvider,
    RenderTask,
    build_provider,
)
from ..memory.repository import Repository
from ..memory.settings_repo import (
    SQLiteSettingsStore,
    load_ai_credentials,
    save_ai_credentials,
    secrets_path,
)
from ..safety.redlines import sanitize_text
from .components import (
    DANGER,
    DANGER_KEY,
    PRIMARY,
    SKELETON_INLINE,
    SKELETON_PANEL,
    button_kwargs,
    loading_skeleton,
)
from .focus_audio import render_focus_audio
from .icons import ICON_CHECK, ICON_ERROR, ICON_INFO
from .milestones import celebrate_mistakes_cleared
from .motion import (
    load_celebration_settings,
    load_dynamic_background,
    save_celebration_settings,
    save_dynamic_background,
)
from .sound import (
    cue_bytes,
    load_sound_settings,
    save_sound_settings,
)
from .theme import (
    DENSITY_COMFORTABLE,
    DENSITY_COMPACT,
    layout_density,
    save_layout_density,
)
from .theme_background import (
    BACKGROUND_OPTIONS,
    inject_background_css,
    load_background,
    save_background,
)

FONT_SIZE_LABELS = {"小": "small", "中": "medium", "大": "large"}
FONT_SIZE_CSS = {
    "small": "html{font-size:14px;}",
    "medium": "html{font-size:16px;}",
    "large": "html{font-size:18px;}",
}
SCHEDULER_LABELS = {
    "FSRS（当前默认）": "fsrs",
    "SM-2（兼容）": "sm2",
}
THEME_LABELS = {
    "浅色": "light",
    "深色": "dark",
    "跟随系统": "system",
}
RESOURCE_NOTICE = (
    "- 背景：Pattern Craft（MIT）\n"
    "- 动效背景：Radiant（MIT）\n"
    "- 庆祝动效：canvas-confetti（ISC）\n"
    "- 反馈音：uisfx（音频 CC0 1.0）\n"
    "- 专注音频：Noisekun / Moodist / Open Lo-Fi（仅外部链接）\n"
    "- CozyPixels：仅参考配色，未使用任何图片\n"
    "- 未集成：css-doodle、streamlit-animate、weft-ui、matanim、"
    "handanim、bgvault、Quiz and Game Show Sound Effects、"
    "math-pattern-gen、tiks"
)
DISCLAIMER_TEXT = """## 免责声明

本项目集成的背景图案、音效与环境音来自第三方开源项目，其许可证以各项目仓库声明为准。我们已尽力核实许可证信息，但**不对第三方资源的版权状态作任何法律保证**，也不构成法律建议。

- CC0 / 公有领域资源：无需署名，但我们仍在 THIRD_PARTY_NOTICES.md 中列出来源以示尊重。
- MIT 资源：保留原版权声明与许可声明。
- 来源不明或许可证不清的资源：一律不使用。

若你是权利人并认为本项目使用不当，请通过仓库 Issue 联系，我们将在核实后移除相关内容。

用户自行选择的外部曲库与外部链接，其许可证与使用条款由对应项目负责，本项目仅提供入口，不承担相关责任。

### 动效与微交互

本项目的动态背景、庆祝动效与微交互参考了第三方开源资源，其许可证以各项目仓库声明为准。我们已尽力核实许可证信息，但**不对第三方资源的版权状态作任何法律保证**，也不构成法律建议。

- MIT / ISC / CC0 / 公有领域资源：按对应许可证使用；需要保留版权声明的，已在 THIRD_PARTY_NOTICES.md 中保留。
- 仅参考设计模式、未引入代码的资源：已注明“仅参考”。
- 来源不明或许可证不清的资源：一律不集成。

若你是权利人并认为本项目使用不当，请通过仓库 Issue 联系，我们将在核实后移除相关内容。

用户自行启用的动效与背景，其性能表现可能因设备而异，本项目不对特定设备上的帧率或耗电作保证。
"""


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
    st.session_state["settings"] = settings
    apply_runtime_settings(
        settings, clear_ai_env=not settings.ai_enabled
    )
    if _is_guest(consent):
        st.session_state["guest_settings"] = settings.to_mapping(
            include_advanced=True
        )
    else:
        store = SQLiteSettingsStore(db_path())
        try:
            store.set_many(settings.to_mapping(include_advanced=True))
        finally:
            store.close()
        load_settings.clear()
    _rebuild_provider()


def apply_runtime_settings(
    settings: AppSettings, *, clear_ai_env: bool = False
) -> None:
    """把设置同步到进程环境变量；不把密钥写入 settings 表。"""
    os.environ["MATHCOACH_SCHEDULER"] = settings.scheduler
    api_key, base_url = load_ai_credentials()
    if settings.ai_enabled and api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            os.environ["OPENAI_BASE_URL"] = base_url
        else:
            os.environ.pop("OPENAI_BASE_URL", None)
    elif clear_ai_env:
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("OPENAI_BASE_URL", None)


def inject_font_size_css(size: str) -> None:
    """注入常量字号与背景 CSS；默认字号不注入，避免无谓的布局变化。"""
    if size != "medium":
        css = FONT_SIZE_CSS.get(size)
        if css:
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    consent = st.session_state.get("consent")
    if consent is not None:
        inject_background_css(consent)


def sanitized_connection_error(exc: Exception, api_key: str) -> str:
    """返回不含 API Key 的连接失败摘要。"""
    message = sanitize_text(str(exc))
    if api_key:
        message = message.replace(api_key, "[已脱敏]")
    return f"{type(exc).__name__}: {message}"[:240]


def _rebuild_provider() -> None:
    provider = build_provider()
    st.session_state.provider = provider
    engine = st.session_state.get("engine")
    if engine is not None:
        engine.provider = provider


@st.fragment
def _render_connection_test(existing_key: str, existing_base: str) -> None:
    st.caption("测试连接不会覆盖已保存的密钥。")
    with st.form("settings_test_connection"):
        key = st.text_input(
            "测试 API Key",
            type="password",
            value="",
            placeholder="留空使用已保存 Key" if existing_key else "",
        )
        base_url = st.text_input("测试 Base URL", value=existing_base)
        submitted = st.form_submit_button("测试连接")
    if not submitted:
        return
    test_key = key.strip() or existing_key
    if not test_key:
        st.warning("请先输入 API Key。")
        return
    try:
        provider = OpenAICompatibleProvider(
            api_key=test_key, base_url=base_url.strip() or None
        )
        with loading_skeleton(SKELETON_INLINE):
            provider.render(
                RenderTask(
                    kind="explain",
                    card_name="连接测试",
                    content="请只回复 OK",
                )
            )
    except Exception as exc:  # noqa: BLE001 - 需要把任意网络/鉴权错误转成页面提示
        st.error(f"连接失败：{sanitized_connection_error(exc, test_key)}")
    else:
        st.success("连接成功。")


def _render_ai_config(
    repository: Repository, consent: Consent, settings: AppSettings
) -> None:
    st.divider()
    st.markdown("### AI 配置")
    st.caption(
        f"API Key 与 Base URL 仅存本机：`{secrets_path()}`；"
        "不会写入 settings 表、导出文件或 git。"
    )
    existing_key, existing_base = load_ai_credentials()
    with st.form("settings_ai_form"):
        api_key = st.text_input(
            "API Key",
            type="password",
            value="",
            placeholder="已保存，留空表示不修改" if existing_key else "",
        )
        base_url = st.text_input("Base URL", value=existing_base)
        saved = st.form_submit_button(
            "保存 AI 配置", **button_kwargs(PRIMARY)
        )
    if saved:
        final_key = api_key.strip() or existing_key
        save_ai_credentials(final_key, base_url)
        repository.record_audit("settings_ai", "ok")
        apply_runtime_settings(settings)
        _rebuild_provider()
        st.session_state["settings_saved"] = True
        st.rerun()
    _render_connection_test(existing_key, existing_base)


def _render_notices() -> None:
    if st.session_state.pop("settings_saved", False):
        st.success("设置已保存。")
    if st.session_state.pop("settings_ratio_saved", False):
        st.success("复习配比已保存。")
    if st.session_state.pop("settings_appearance_saved", False):
        st.success("外观设置已保存。")
    if st.session_state.pop("settings_sound_saved", False):
        st.success("声音设置已保存。")
    if st.session_state.pop("settings_motion_saved", False):
        st.success("动效设置已保存。")
    if st.session_state.pop("settings_focus_audio_saved", False):
        st.success("专注音频设置已保存。")
    cleared = st.session_state.pop("settings_cleared", None)
    if cleared is not None:
        st.success(f"学习数据已清除，共删除 {cleared} 条记录。")


def _render_export(repository: Repository, consent: Consent) -> None:
    st.divider()
    st.markdown("### 导出学习数据")
    if _is_guest(consent):
        st.info(f"{ICON_INFO} 游客模式没有持久学习数据可导出。")
        return

    with loading_skeleton(SKELETON_PANEL):
        receipts = repository.list_receipts(limit=None)
        mistakes = repository.list_mistakes(limit=None)
        review_items = repository.list_review_items()
        now = datetime.now(UTC)
        stamp = now.strftime("%Y%m%d-%H%M%S")
        settings = current_settings(consent)
        payload_json = export_json(
            receipts=receipts,
            mistakes=mistakes,
            review_items=review_items,
            settings=settings,
            now=now,
        )
        payload_receipts = export_receipts_csv(receipts)
        payload_mistakes = export_mistakes_csv(mistakes)
        payload_markdown = export_markdown(
            receipts=receipts,
            mistakes=mistakes,
            settings=settings,
            now=now,
        )
    st.caption("导出不包含 API 密钥、secrets 文件或审计日志。")
    st.download_button(
        "下载完整 JSON",
        data=payload_json,
        file_name=f"mathcoach-{stamp}.json",
        mime="application/json",
        key="settings_export_json",
    )
    left, right = st.columns(2)
    with left:
        st.download_button(
            "下载收据 CSV",
            data=payload_receipts,
            file_name=f"mathcoach-receipts-{stamp}.csv",
            mime="text/csv",
            key="settings_export_receipts",
        )
    with right:
        st.download_button(
            "下载错题 CSV",
            data=payload_mistakes,
            file_name=f"mathcoach-mistakes-{stamp}.csv",
            mime="text/csv",
            key="settings_export_mistakes",
        )
    st.download_button(
        "下载 Markdown 报告",
        data=payload_markdown,
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
        submitted = st.form_submit_button(
            "永久清除学习数据",
            key=DANGER_KEY,
            **button_kwargs(DANGER),
        )
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
    celebrate_mistakes_cleared(consent, counts.get("mistakes", 0))
    repository.record_audit("settings_clear", "ok")
    st.session_state["settings_cleared"] = sum(counts.values())
    st.rerun()


def _render_audit(repository: Repository, consent: Consent) -> None:
    st.divider()
    st.markdown("### 安全审计日志（只读）")
    entries = repository.list_audit(limit=200)
    if not entries:
        st.caption("暂无审计记录。")
        return
    rows = [
        {
            "id": entry.id,
            "时间": entry.created_at.isoformat(),
            "操作": sanitize_text(entry.op),
            "结果": sanitize_text(entry.result),
        }
        for entry in entries
    ]
    with st.expander("查看审计日志", expanded=False):
        st.dataframe(rows, hide_index=True)
    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    st.download_button(
        "下载审计 CSV",
        data=export_audit_csv(entries),
        file_name=f"mathcoach-audit-{stamp}.csv",
        mime="text/csv",
        key="settings_audit_csv",
    )
    st.download_button(
        "下载审计 JSON",
        data=export_audit_json(entries, now),
        file_name=f"mathcoach-audit-{stamp}.json",
        mime="application/json",
        key="settings_audit_json",
    )
    st.caption("审计日志只读；不包含 Token 或学习内容。")


def _render_dev_panel(consent: Consent, settings: AppSettings) -> None:
    st.divider()
    with st.expander("开发者信息（只读）", expanded=False):
        st.caption(
            f"存储后端：{'游客内存' if _is_guest(consent) else 'SQLite'}"
        )
        if not _is_guest(consent):
            st.caption(f"数据库路径：{db_path()}")
        st.caption(
            f"MATHCOACH_CONTENT_STRICT：{'1' if content_strict() else '0'}"
        )
        st.caption(
            "调度环境："
            f"{os.environ.get('MATHCOACH_SCHEDULER', 'fsrs')}"
        )
        st.caption(
            f"主题偏好：{settings.theme}（需重启或手动修改 "
            ".streamlit/config.toml 生效）"
        )
        st.caption("本面板只读，不提供写入口。")


def _render_appearance_form(
    repository: Repository, consent: Consent
) -> None:
    st.markdown("### 外观")
    st.caption(
        "背景默认关闭；仅使用常量 CSS，不加载外部图片。"
        "背景随实际生效的浅色/深色主题切换，主题变更需重启。"
    )
    current = load_background(consent)
    current_dynamic = load_dynamic_background(consent)
    current_density = layout_density(consent)
    labels = list(BACKGROUND_OPTIONS.values())
    keys = list(BACKGROUND_OPTIONS)
    index = keys.index(current) if current in keys else 0
    with st.form("settings_appearance_form"):
        label = st.selectbox(
            "背景",
            labels,
            index=index,
            key="settings_background",
        )
        dynamic_background = st.toggle(
            "动态背景（实验性）",
            value=current_dynamic,
            key="settings_dynamic_background",
            help="仅在仪表盘和空状态显示；默认关闭。",
        )
        compact_layout = st.toggle(
            "紧凑布局",
            value=current_density == DENSITY_COMPACT,
            key="settings_compact_layout",
            help="减少区块间距；保存后立即生效。",
        )
        saved = st.form_submit_button(
            "保存外观设置", **button_kwargs(PRIMARY)
        )
    if not saved:
        return
    choice = keys[labels.index(label)]
    background_saved = save_background(consent, choice)
    motion_saved = save_dynamic_background(consent, dynamic_background)
    density_saved = save_layout_density(
        consent,
        DENSITY_COMPACT if compact_layout else DENSITY_COMFORTABLE,
    )
    if background_saved and motion_saved and density_saved:
        repository.record_audit("settings_appearance", "ok")
        st.session_state["settings_appearance_saved"] = True
        st.rerun()
    else:
        st.error(f"{ICON_ERROR} 外观设置保存失败，请重试。")


def _render_sound_form(
    repository: Repository, consent: Consent
) -> None:
    st.markdown("### 声音")
    st.caption(
        "默认关闭；音量由浏览器原生播放器控制。"
        "首次播放需要你点击；不会在进入应用时自动播放。"
    )
    current = load_sound_settings(consent)
    with st.form("settings_sound_form"):
        enabled = st.toggle(
            "启用声音",
            value=current.enabled,
            key="settings_sound_enabled",
        )
        feedback = st.toggle(
            "答题反馈音",
            value=current.feedback_enabled,
            key="settings_feedback_enabled",
        )
        saved = st.form_submit_button(
            "保存声音设置", **button_kwargs(PRIMARY)
        )
    if saved:
        if save_sound_settings(
            consent,
            enabled=enabled,
            feedback_enabled=feedback,
        ):
            repository.record_audit("settings_sound", "ok")
            st.session_state["settings_sound_saved"] = True
            st.rerun()
        else:
            st.error(f"{ICON_ERROR} 声音设置保存失败，请重试。")
    st.caption("试听使用原生播放器；浏览器可能拦截自动播放。")
    if st.button("试听正确音", key="sound_preview_correct"):
        if not current.enabled:
            st.info("请先启用声音并保存。")
        else:
            st.audio(
                cue_bytes("correct"),
                format="audio/mpeg",
                autoplay=True,
            )
    if st.button("试听点击音", key="sound_preview_click"):
        if not current.enabled:
            st.info("请先启用声音并保存。")
        else:
            st.audio(
                cue_bytes("click"),
                format="audio/mpeg",
                autoplay=True,
            )


def _render_about() -> None:
    with st.expander("关于 / 致谢", expanded=False):
        st.markdown("**第三方资源**")
        st.markdown(RESOURCE_NOTICE)
        st.caption(
            "完整清单见仓库根目录 THIRD_PARTY_NOTICES.md；"
            "核实人：待人工复核。"
        )
        st.markdown(DISCLAIMER_TEXT)


def _render_motion_form(
    repository: Repository, consent: Consent
) -> None:
    st.markdown("### 动效")
    st.caption(
        "庆祝动效默认开启；减少动效优先；动态背景默认关闭。"
        "浏览器 prefers-reduced-motion 也会禁用动画。"
    )
    current = load_celebration_settings(consent)
    with st.form("settings_motion_form"):
        celebrations = st.toggle(
            "庆祝动效",
            value=current.enabled,
            key="settings_celebrations",
        )
        reduce_motion = st.toggle(
            "减少动效",
            value=current.reduce_motion,
            key="settings_reduce_motion",
        )
        saved = st.form_submit_button(
            "保存动效设置", **button_kwargs(PRIMARY)
        )
    if saved:
        if save_celebration_settings(
            consent,
            enabled=celebrations,
            reduce_motion=reduce_motion,
        ):
            repository.record_audit("settings_motion", "ok")
            st.session_state["settings_motion_saved"] = True
            st.rerun()
        else:
            st.error(f"{ICON_ERROR} 动效设置保存失败，请重试。")


def _render_review_ratio_form(
    repository: Repository, consent: Consent, settings: AppSettings
) -> None:
    st.markdown("### 复习配比")
    st.caption("先修缺口 1 + 错题变式 1 固定；其余题位按新卡占比分配。")
    with st.form("settings_review_ratio_form"):
        ratio = st.slider(
            "新卡占比（%）",
            min_value=0,
            max_value=100,
            value=settings.new_review_ratio,
            step=5,
            key="settings_new_review_ratio",
            help=(
                "新卡占比越高，复习包中新卡越多；"
                "先修缺口 1 与错题变式 1 固定，其余题位按比例分配。"
                "0% 即保持到期 3 + 新卡 0 的 1+3+1 结构。"
            ),
        )
        st.caption("范围 0–100，步长 5；0% 保持 1+3+1。")
        saved = st.form_submit_button(
            "保存复习配比", **button_kwargs(PRIMARY)
        )
    if saved:
        new_settings = replace(settings, new_review_ratio=int(ratio))
        _save_settings(consent, new_settings)
        repository.record_audit("settings_review_ratio", "ok")
        st.session_state["settings_ratio_saved"] = True
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

    _render_ai_config(repository, consent, settings)

    st.markdown("### 基础设置")
    current_scheduler = next(
        label
        for label, value in SCHEDULER_LABELS.items()
        if value == settings.scheduler
    )
    current_font = next(
        label
        for label, value in FONT_SIZE_LABELS.items()
        if value == settings.font_size
    )
    current_theme = next(
        label
        for label, value in THEME_LABELS.items()
        if value == settings.theme
    )
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
        scheduler_label = st.radio(
            "调度算法",
            list(SCHEDULER_LABELS),
            index=list(SCHEDULER_LABELS).index(current_scheduler),
            horizontal=True,
            key="settings_scheduler",
        )
        st.caption("仅影响后续复习调度，不改写历史收据。")
        font_label = st.select_slider(
            "界面字号",
            options=list(FONT_SIZE_LABELS),
            value=current_font,
            key="settings_font_size",
        )
        theme_label = st.selectbox(
            "主题",
            list(THEME_LABELS),
            index=list(THEME_LABELS).index(current_theme),
            key="settings_theme",
        )
        st.caption(
            "主题需重启应用或手动修改 .streamlit/config.toml 生效，"
            "不做即时切换。"
        )
        reminder_enabled = st.toggle(
            "复习提醒",
            value=settings.reminder_enabled,
            key="settings_reminder_enabled",
        )
        reminder_time = st.time_input(
            "提醒时间",
            value=dt_time.fromisoformat(settings.reminder_time),
            key="settings_reminder_time",
        )
        st.caption("提醒仅在应用打开时生效，不发送系统通知。")
        with st.expander("高级参数（默认锁定）"):
            st.caption(
                f"FSRS 目标记忆率：{DEFAULT_PARAMS.desired_retention}"
            )
            st.caption(f"最大复习间隔：{DEFAULT_PARAMS.max_interval_days} 天")
            st.caption("高级参数使用内置默认值，当前不可编辑。")
        saved = st.form_submit_button(
            "保存设置", **button_kwargs(PRIMARY)
        )
    if saved:
        new_settings = AppSettings(
            ai_enabled=ai_enabled,
            daily_review_limit=int(daily_limit),
            new_review_ratio=settings.new_review_ratio,
            scheduler=SCHEDULER_LABELS[scheduler_label],
            font_size=FONT_SIZE_LABELS[font_label],
            theme=THEME_LABELS[theme_label],
            reminder_enabled=reminder_enabled,
            reminder_time=reminder_time.strftime("%H:%M"),
        )
        scheduler_changed = new_settings.scheduler != settings.scheduler
        _save_settings(consent, new_settings)
        repository.record_audit("settings_save", "ok")
        if scheduler_changed:
            repository.record_audit("settings_scheduler", "ok")
        st.session_state["settings_saved"] = True
        st.rerun()

    if offline and settings.ai_enabled:
        st.warning(
            "已启用 AI 模式，但当前未检测到可用 API Key；"
            "请在 AI 配置中填写密钥，或关闭 AI 模式。"
        )
    elif offline:
        st.caption("未配置 API Key 时使用离线模板，判分逻辑不变。")

    _render_appearance_form(repository, consent)
    _render_sound_form(repository, consent)
    _render_motion_form(repository, consent)
    render_focus_audio(repository, consent)
    _render_review_ratio_form(repository, consent, settings)
    _render_export(repository, consent)
    _render_clear(repository, consent)
    _render_audit(repository, consent)
    _render_dev_panel(consent, settings)
    _render_about()
