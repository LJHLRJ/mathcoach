"""交互改造回归：目标 form 与倒计时 fragment。"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_goal_form_submits_without_extra_click(tmp_path, monkeypatch):
    """目标表单提交后无需额外点击。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "goal-form.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()

    assert not at.exception
    at.text_input(key="goal_input").set_value("搞懂度量空间")
    at.button(key="confirm_goal").click()
    at.run()

    assert not at.exception
    assert not any(
        text_input.key == "goal_input" for text_input in at.text_input
    )


def test_goal_form_and_countdown_are_configured():
    """表单与倒计时 fragment 配置存在。"""
    source = APP_PATH.read_text(encoding="utf-8")

    assert 'st.form(\n                "goal_form"' in source
    assert "enter_to_submit=False" in source
    assert "@st.fragment(run_every=5)" in source
    assert "_render_quiz_countdown(state)" in source


def test_collapsed_audit_expander_skips_database_query():
    """折叠的审计面板不查询数据库。"""
    at = AppTest.from_string(
        "import streamlit as st\n"
        "from mathcoach.domain.models import Consent\n"
        "from mathcoach.ui.settings import _render_audit\n"
        "class Repo:\n"
        "    calls = 0\n"
        "    def list_audit(self, limit=200):\n"
        "        Repo.calls += 1\n"
        "        return []\n"
        "_render_audit(Repo(), Consent())\n"
        "st.session_state['audit_calls'] = Repo.calls\n"
    )
    at.run()

    assert not at.exception
    assert at.session_state["audit_calls"] == 0


def test_settings_reads_are_cached_per_session():
    """设置读取按会话缓存。"""
    at = AppTest.from_string(
        "import streamlit as st\n"
        "from mathcoach.domain.models import Consent\n"
        "from mathcoach.ui import motion, theme_background\n"
        "class Store:\n"
        "    opens = 0\n"
        "    def __init__(self, path):\n"
        "        Store.opens += 1\n"
        "    def get_all(self):\n"
        "        return {}\n"
        "    def close(self):\n"
        "        pass\n"
        "theme_background.SQLiteSettingsStore = Store\n"
        "motion.SQLiteSettingsStore = Store\n"
        "consent = Consent(memory=True, mistake_book=True)\n"
        "theme_background.load_background(consent)\n"
        "theme_background.load_background(consent)\n"
        "motion.load_celebration_settings(consent)\n"
        "motion.load_celebration_settings(consent)\n"
        "st.session_state['opens'] = Store.opens\n"
    )
    at.run()

    assert not at.exception
    assert at.session_state["opens"] == 2


def test_mistake_gap_helper_reuses_precomputed_stats():
    """错题缺口复用预计算统计。"""
    source = APP_PATH.read_text(encoding="utf-8")

    assert "def _gaps_from_stats" in source
    assert "_gaps_from_stats(stats, active_mistakes, entry.card_id)" in source
    assert "gaps = _collect_gaps(repository, entry.card_id)" not in source


def test_settings_export_is_generated_on_demand(tmp_path, monkeypatch):
    """导出数据按需生成。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "export.sqlite3"))
    at = AppTest.from_string(
        "import streamlit as st\n"
        "from mathcoach.domain.models import Consent\n"
        "from mathcoach.ui.settings import _render_export\n"
        "class Repo:\n"
        "    def list_receipts(self, limit=None):\n"
        "        return []\n"
        "    def list_mistakes(self, limit=None, include_mastered=True):\n"
        "        return []\n"
        "    def list_review_items(self):\n"
        "        return []\n"
        "_render_export(Repo(), Consent(memory=True, mistake_book=True))\n"
    )
    at.run()

    assert not at.exception
    assert not [
        button for button in at.download_button
        if button.label == "下载完整 JSON"
    ]
    at.button(key="settings_prepare_export").click()
    at.run()

    assert not at.exception
    assert [
        button for button in at.download_button
        if button.label == "下载完整 JSON"
    ]
    assert at.button(key="settings_prepare_export").label == (
        "生成 / 刷新导出数据"
    )
