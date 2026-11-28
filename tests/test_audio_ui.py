"""反馈音效：默认关闭、内嵌 cue 与设置开关。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import Consent
from mathcoach.ui import sound
from mathcoach.ui.sound import (
    SoundSettings,
    cue_bytes,
    cue_html,
    load_sound_settings,
    save_sound_settings,
)

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PERSISTENT = Consent(memory=True, mistake_book=True)


def test_sound_defaults_to_disabled(tmp_path):
    """声音默认关闭，反馈音默认开启。"""
    assert load_sound_settings(
        PERSISTENT, tmp_path / "missing" / "x.sqlite3"
    ) == SoundSettings()
    assert SoundSettings().enabled is False
    assert SoundSettings().feedback_enabled is True


def test_sound_settings_persist(tmp_path):
    """声音设置可持久化并读回。"""
    path = tmp_path / "sound.sqlite3"

    assert load_sound_settings(PERSISTENT, path) == SoundSettings()
    assert save_sound_settings(
        PERSISTENT,
        enabled=True,
        feedback_enabled=False,
        path=path,
    )
    assert load_sound_settings(PERSISTENT, path) == SoundSettings(
        enabled=True,
        feedback_enabled=False,
    )


def test_embedded_cues_are_valid_and_small():
    """内嵌提示音均为合法 MP3 且总体积受限。"""
    expected = {
        "correct": 7984,
        "wrong": 6939,
        "complete": 8611,
        "click": 4013,
    }

    assert set(sound.CUE_B64) == set(expected)
    for kind, size in expected.items():
        data = cue_bytes(kind)
        assert len(data) == size
        assert data.startswith(b"ID3")
    assert sum(expected.values()) < 50_000
    assert "CC0" in (sound.__doc__ or "")


def test_cue_html_is_hidden_and_has_no_external_url():
    """提示音 HTML 隐藏且不含外部链接。"""
    html = cue_html("correct")

    assert "<audio" in html
    assert "autoplay" in html
    assert "display:none" in html
    assert "data:audio/mpeg;base64," in html
    assert "http://" not in html
    assert "https://" not in html
    assert cue_html("unknown") == ""


def test_settings_page_shows_sound_controls(tmp_path, monkeypatch):
    """设置页展示声音开关与保存按钮。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "sound-ui.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    labels = {toggle.label for toggle in at.toggle}
    assert "启用声音" in labels
    assert "答题反馈音" in labels
    assert any(button.label == "保存声音设置" for button in at.button)


def _complete_first_loop(at: AppTest) -> None:
    """完成一次最小学习闭环。"""
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数")
    at.button[0].click().run()
    at.button[0].click().run()
    at.radio[0].set_value("y = x²")
    at.button[0].click().run()


def test_sound_disabled_does_not_render_audio(tmp_path, monkeypatch):
    """关闭声音时不渲染音频。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "sound-off.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    _complete_first_loop(at)

    assert not at.exception
    assert not any(
        "data:audio/mpeg;base64," in markdown.value
        for markdown in at.markdown
    )


def test_sound_enabled_renders_feedback_audio(tmp_path, monkeypatch):
    """开启声音后渲染反馈音频。"""
    path = tmp_path / "sound-on.sqlite3"
    assert save_sound_settings(
        PERSISTENT,
        enabled=True,
        feedback_enabled=True,
        path=path,
    )
    monkeypatch.setenv("MATHCOACH_DB", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    _complete_first_loop(at)

    assert not at.exception
    assert any(
        "data:audio/mpeg;base64," in markdown.value
        for markdown in at.markdown
    )
