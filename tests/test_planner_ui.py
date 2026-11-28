"""智能练习册 UI：模式入口、计划摘要与只读预览。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_planner_mode_renders_plan(tmp_path, monkeypatch) -> None:
    """进入智能练习册后展示计划摘要与选题理由。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv("MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3"))
    monkeypatch.setenv("MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3"))

    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    at.selectbox[1].select("智能练习册").run()

    assert not at.exception
    assert any(
        subheader.value == "智能练习册" for subheader in at.subheader
    )
    assert any(expander.label == "选题理由" for expander in at.expander)
    assert any("题目" in metric.label for metric in at.metric)
