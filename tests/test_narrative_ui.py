"""叙事 UI：仪表盘只显示已点亮与下一节点，设置可关闭。"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _dashboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """启动应用并切换到仪表盘页。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[1].select("仪表盘").run()
    return at


def test_dashboard_shows_narrative_and_next_node(tmp_path, monkeypatch):
    """开启叙事时仪表盘显示进度与下一节点。"""
    at = _dashboard(tmp_path, monkeypatch)

    assert not at.exception
    assert any("叙事进度" in markdown.value for markdown in at.markdown)
    assert any("下一节点" in caption.value for caption in at.caption)


def test_dashboard_hides_narrative_when_disabled(tmp_path, monkeypatch):
    """关闭叙事开关后隐藏叙事区域，其余指标保留。"""
    at = _dashboard(tmp_path, monkeypatch)
    at.toggle[2].set_value(False).run()
    at.selectbox[1].select("仪表盘").run()

    assert not at.exception
    assert not any("叙事进度" in markdown.value for markdown in at.markdown)
    assert any(metric.label == "收据总数" for metric in at.metric)


def test_receipt_shows_narrative_feedback(tmp_path, monkeypatch):
    """完成一次练习后收据展示叙事反馈。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数")
    at.button[0].click().run()
    at.button[0].click().run()
    at.radio[0].set_value("y = x²")
    at.button[0].click().run()

    assert not at.exception
    assert any("叙事：" in caption.value for caption in at.caption)
