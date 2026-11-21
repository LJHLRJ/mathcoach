"""背景主题：默认关闭、常量 CSS 与设置持久化。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import Consent
from mathcoach.ui.theme_background import (
    BACKGROUND_OPTIONS,
    background_css,
    load_background,
    save_background,
)

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PERSISTENT = Consent(memory=True, mistake_book=True)
GUEST = Consent(memory=False, mistake_book=False)


def test_default_background_is_none():
    assert set(BACKGROUND_OPTIONS) == {
        "none",
        "paper",
        "dots",
        "diagonal",
    }
    assert background_css("none") == ""
    assert load_background(GUEST) == "none"


def test_background_css_is_constant_and_has_no_external_assets():
    for choice in ("paper", "dots", "diagonal"):
        for theme in ("light", "dark"):
            css = background_css(choice, theme)
            assert ".stApp" in css
            assert "<script" not in css.lower()
            assert "url(" not in css.lower()

    assert background_css("paper", "light") != background_css("paper", "dark")
    assert background_css("unknown") == ""


def test_background_choice_persists_in_settings_store(tmp_path):
    path = tmp_path / "background.sqlite3"

    assert load_background(PERSISTENT, path) == "none"
    assert save_background(PERSISTENT, "paper", path) is True
    assert load_background(PERSISTENT, path) == "paper"

    assert save_background(PERSISTENT, "unknown", path) is False
    assert load_background(PERSISTENT, path) == "paper"


def test_settings_page_shows_background_selector(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "background-ui.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    assert any(box.label == "背景" for box in at.selectbox)
    assert any(
        button.label == "保存外观设置" for button in at.button
    )


def test_background_is_injected_after_persisted_selection(tmp_path, monkeypatch):
    path = tmp_path / "background-injected.sqlite3"
    assert save_background(PERSISTENT, "paper", path) is True
    monkeypatch.setenv("MATHCOACH_DB", str(path))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    assert not at.exception
    assert any(".stApp" in markdown.value for markdown in at.markdown)
