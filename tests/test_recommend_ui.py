"""仪表盘下一步推荐：展示 3 张卡片、理由与依据。"""
from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.memory.sqlite_repo import SQLiteRepository

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_shows_three_recommendations(tmp_path, monkeypatch):
    """仪表盘展示三条推荐，每条都带依据。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[1].select("仪表盘").run()

    assert not at.exception
    assert any("下一步推荐" in markdown.value for markdown in at.markdown)
    basis_lines = [
        caption.value for caption in at.caption if "依据：" in caption.value
    ]
    assert len(basis_lines) == 3


def test_dashboard_recommendation_prefers_low_mastery(tmp_path, monkeypatch):
    """掌握度更低的卡片排在推荐首位。"""
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    now = datetime.now(timezone.utc)
    repository.set_mastery("hs-function-intro-001", 0.9, now)
    repository.set_mastery("hs-set-001", 0.05, now)
    repository.close()

    monkeypatch.setenv("MATHCOACH_DB", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[1].select("仪表盘").run()

    assert not at.exception
    values = [markdown.value for markdown in at.markdown]
    start = values.index("**下一步推荐**")
    assert values[start + 1].startswith("- hs-set-001")


def test_dashboard_recommend_button_starts_session(tmp_path, monkeypatch):
    """点击推荐开始按钮进入陪练并预选对应卡片。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[1].select("仪表盘").run()

    values = [markdown.value for markdown in at.markdown]
    start = values.index("**下一步推荐**")
    card_id = values[start + 1].split("：", 1)[0].removeprefix("- ")

    next(
        button
        for button in at.button
        if button.label.startswith("推荐开始")
    ).click().run()

    assert not at.exception
    assert at.session_state["app_mode"] == "陪练"
    assert at.session_state["main_tabs"] == "当前任务"
    assert at.selectbox[0].value == card_id
    assert any(box.label == "今天想练到什么？" for box in at.text_input)
