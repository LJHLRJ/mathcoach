"""专注音频：默认关闭、外部链接与来源声明。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import Consent
from mathcoach.ui.focus_audio import (
    FOCUS_SOURCES,
    load_focus_enabled,
    save_focus_enabled,
)

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PERSISTENT = Consent(memory=True, mistake_book=True)


def test_focus_audio_defaults_to_disabled(tmp_path):
    assert load_focus_enabled(PERSISTENT, tmp_path / "focus.sqlite3") is False


def test_focus_audio_toggle_persists(tmp_path):
    path = tmp_path / "focus.sqlite3"

    assert save_focus_enabled(PERSISTENT, True, path) is True
    assert load_focus_enabled(PERSISTENT, path) is True
    assert save_focus_enabled(PERSISTENT, False, path) is True
    assert load_focus_enabled(PERSISTENT, path) is False


def test_focus_sources_use_verified_https_urls():
    names = {source.name for source in FOCUS_SOURCES}

    assert names == {"Noisekun", "Moodist", "Open Lo-Fi"}
    for source in FOCUS_SOURCES:
        assert source.url.startswith("https://")
        assert source.repository.startswith("https://")
        assert source.license_note


def test_settings_page_shows_focus_audio_section(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "focus-ui.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    markdown = " ".join(element.value for element in at.markdown)
    assert "专注音频" in markdown
    assert any(
        toggle.label == "显示专注音频外部入口" for toggle in at.toggle
    )


def test_enabled_focus_audio_shows_external_sources(tmp_path, monkeypatch):
    path = tmp_path / "focus-enabled.sqlite3"
    assert save_focus_enabled(PERSISTENT, True, path) is True
    monkeypatch.setenv("MATHCOACH_DB", str(path))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    captions = " ".join(caption.value for caption in at.caption)
    assert "Noisekun" in captions
    assert "Moodist" in captions
    assert "Open Lo-Fi" in captions
