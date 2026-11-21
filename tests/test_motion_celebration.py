"""庆祝动效：默认开启、减少动效优先、全屏 iframe 常量。"""
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import Consent
from mathcoach.ui import motion
from mathcoach.ui.motion import CelebrationSettings

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PERSISTENT = Consent(memory=True, mistake_book=True)


def test_celebration_defaults_on():
    assert motion.CelebrationSettings() == CelebrationSettings(
        enabled=True,
        reduce_motion=False,
    )


def test_celebration_settings_persist(tmp_path):
    path = tmp_path / "celebration.sqlite3"

    assert motion.load_celebration_settings(PERSISTENT, path) == (
        CelebrationSettings()
    )
    assert motion.save_celebration_settings(
        PERSISTENT,
        enabled=False,
        reduce_motion=True,
        path=path,
    )
    assert motion.load_celebration_settings(PERSISTENT, path) == (
        CelebrationSettings(enabled=False, reduce_motion=True)
    )


def test_celebration_iframe_is_local_constant():
    html = motion.CELEBRATION_IFRAME

    assert 'src="/app/static/overlay/confetti.html"' in html
    assert "position:fixed" in html
    assert "pointer-events:none" in html
    assert "http://" not in html
    assert "https://" not in html


def test_micro_interactions_respect_reduced_motion():
    css = motion.MICRO_INTERACTIONS_CSS

    assert "prefers-reduced-motion" in css
    assert "transition" in css
    assert "button" in css


def test_queue_celebration_respects_settings(monkeypatch):
    fake_state = {}
    monkeypatch.setattr(
        motion,
        "st",
        SimpleNamespace(session_state=fake_state),
    )
    monkeypatch.setattr(
        motion,
        "load_celebration_settings",
        lambda consent: CelebrationSettings(True, False),
    )
    motion.queue_celebration("five-correct", PERSISTENT)
    assert fake_state.get("pending_celebration") == "five-correct"

    fake_state.clear()
    monkeypatch.setattr(
        motion,
        "load_celebration_settings",
        lambda consent: CelebrationSettings(True, True),
    )
    motion.queue_celebration("five-correct", PERSISTENT)
    assert "pending_celebration" not in fake_state


def test_play_pending_celebration_renders_iframe(monkeypatch):
    fake_state = {"pending_celebration": "review-complete"}
    calls = []
    monkeypatch.setattr(
        motion,
        "st",
        SimpleNamespace(
            session_state=fake_state,
            markdown=lambda *args, **kwargs: calls.append((args, kwargs)),
        ),
    )
    monkeypatch.setattr(
        motion,
        "load_celebration_settings",
        lambda consent: CelebrationSettings(True, False),
    )

    motion.play_pending_celebration(PERSISTENT)

    assert len(calls) == 1
    assert "iframe" in calls[0][0][0]
    assert "pending_celebration" not in fake_state


def test_settings_page_shows_motion_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "motion-controls.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    labels = {toggle.label for toggle in at.toggle}
    assert "庆祝动效" in labels
    assert "减少动效" in labels
    assert any(button.label == "保存动效设置" for button in at.button)


def test_app_renders_confetti_iframe_when_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "celebration.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    at.session_state["pending_celebration"] = "review-complete"
    at.run()

    assert not at.exception
    assert any(
        "motion-confetti" in markdown.value for markdown in at.markdown
    )
