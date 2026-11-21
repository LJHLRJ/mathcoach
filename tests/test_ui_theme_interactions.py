"""交互改造回归：目标 form 与倒计时 fragment。"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_goal_form_submits_without_extra_click(tmp_path, monkeypatch):
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
    source = APP_PATH.read_text(encoding="utf-8")

    assert 'st.form(\n                "goal_form"' in source
    assert "enter_to_submit=False" in source
    assert "@st.fragment(run_every=5)" in source
    assert "_render_quiz_countdown(state)" in source
