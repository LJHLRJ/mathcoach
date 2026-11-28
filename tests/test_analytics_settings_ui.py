"""设置页暴露独立的在线学情分析开关与凭据入口。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_settings_page_shows_analysis_switch_and_credentials(
    tmp_path, monkeypatch
):
    """设置页展示分析开关与独立凭据表单。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "analysis-ui.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    assert any(
        toggle.label == "启用在线学情分析" for toggle in at.toggle
    )
    assert any(
        box.label == "分析 API Key" for box in at.text_input
    )
    assert any(
        button.label == "保存分析 AI 配置" for button in at.button
    )
