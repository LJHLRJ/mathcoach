"""提示页在表示降级后展示知识点具体例子。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _click(at: AppTest, label: str) -> None:
    """按按钮文本点击并重跑；文本可含图标后的部分。"""
    next(button for button in at.button if label in button.label).click().run()
    assert not at.exception


def test_hint_shows_worked_example_after_repeated_errors(
    tmp_path, monkeypatch
) -> None:
    """连错并请求过提示后，提示页出现具体例子。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15).run()
    at.selectbox[0].select("hs-function-intro-001").run()
    assert not at.exception

    at.text_input[0].set_value("搞懂函数的概念")
    _click(at, "确认目标")
    _click(at, "开始小测")

    at.radio[0].set_value("y² = x")
    _click(at, "提交答案")
    _click(at, "再试一次")
    _click(at, "给步骤")
    _click(at, "再试一次")

    at.radio[0].set_value("x = 1")
    _click(at, "提交答案")
    _click(at, "确认错因")

    markdown = " ".join(item.value for item in at.markdown)
    assert "换成具体例子" in markdown
    assert "y = x² 是函数" in markdown
