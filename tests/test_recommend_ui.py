"""仪表盘下一步推荐：展示 3 张卡片、理由与依据。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_shows_three_recommendations(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[1].select("仪表盘").run()

    assert not at.exception
    assert any("下一步推荐" in markdown.value for markdown in at.markdown)
    recommendation_lines = [
        markdown.value for markdown in at.markdown if "依据：" in markdown.value
    ]
    assert len(recommendation_lines) == 3
