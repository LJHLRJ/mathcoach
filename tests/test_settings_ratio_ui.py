"""复习配比独立表单 UI。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_review_ratio_has_independent_form_and_help(tmp_path, monkeypatch):
    """配比表单独立呈现，并带范围说明与保存按钮。"""
    path = tmp_path / "ratio-ui.sqlite3"
    monkeypatch.setenv("MATHCOACH_DB", str(path))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    markdown = " ".join(element.value for element in at.markdown)
    slider = next(
        element
        for element in at.slider
        if element.label == "新卡占比（%）"
    )
    assert "### 复习配比" in markdown
    assert slider.key == "settings_new_review_ratio"
    assert "先修缺口 1" in slider.help
    captions = " ".join(element.value for element in at.caption)
    assert "范围 0–100，步长 5" in captions
    assert any(button.label == "保存复习配比" for button in at.button)
