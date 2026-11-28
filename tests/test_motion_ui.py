"""动态背景：默认关闭、常量 shader 与 reduced-motion。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import Consent
from mathcoach.ui import motion

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PERSISTENT = Consent(memory=True, mistake_book=True)


def test_dynamic_background_defaults_off(tmp_path):
    """动态背景默认关闭。"""
    assert (
        motion.load_dynamic_background(
            PERSISTENT, tmp_path / "motion.sqlite3"
        )
        is False
    )


def test_dynamic_background_persists(tmp_path):
    """动态背景开关可持久化并读回。"""
    path = tmp_path / "motion.sqlite3"

    assert motion.save_dynamic_background(PERSISTENT, True, path) is True
    assert motion.load_dynamic_background(PERSISTENT, path) is True
    assert motion.save_dynamic_background(PERSISTENT, False, path) is True
    assert motion.load_dynamic_background(PERSISTENT, path) is False


def test_shader_html_is_local_constant_and_respects_reduced_motion():
    """shader HTML 本地内联、常量且响应减少动效。"""
    for variant in ("dashboard", "empty"):
        html = motion.shader_html(variant)
        assert "<canvas" in html
        assert "prefers-reduced-motion" in html
        assert "requestAnimationFrame" in html
        assert "http://" not in html
        assert "https://" not in html
        assert "src=" not in html


def test_render_dynamic_background_is_noop_when_disabled(monkeypatch):
    """关闭时不渲染任何 iframe。"""
    calls = []
    monkeypatch.setattr(
        motion.st.components.v1,
        "html",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(motion, "load_dynamic_background", lambda consent: False)

    motion.render_dynamic_background(PERSISTENT)

    assert calls == []


def test_render_dynamic_background_when_enabled(monkeypatch):
    """开启时渲染一次高度 180 的 iframe。"""
    calls = []
    monkeypatch.setattr(
        motion.st.components.v1,
        "html",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(motion, "load_dynamic_background", lambda consent: True)

    motion.render_dynamic_background(PERSISTENT, "dashboard")

    assert len(calls) == 1
    html, kwargs = calls[0]
    assert "<canvas" in html[0]
    assert kwargs["height"] == 180


def test_settings_page_shows_dynamic_background_toggle(tmp_path, monkeypatch):
    """设置页展示动态背景开关。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "motion-ui.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    assert any(
        toggle.label == "动态背景（实验性）" for toggle in at.toggle
    )
