"""提示页 REMSJ 阶段标签：与现有提示层级对齐。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_hint_shows_remsj_stage(tmp_path, monkeypatch) -> None:
    """第一次答错进入 L2 提示时显示“提取条件”阶段。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    monkeypatch.setenv(
        "MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=20).run()

    at.selectbox[0].select("hs-trig-004").run()
    at.text_input[0].set_value("搞懂正弦型函数")
    next(
        button for button in at.button if button.label == "确认目标"
    ).click().run()
    next(
        button for button in at.button if button.label == "开始小测"
    ).click().run()
    next(
        button for button in at.button if button.label == "提交答案"
    ).click().run()
    next(
        button for button in at.button if button.label == "继续"
    ).click().run()

    next(
        box for box in at.text_input if box.label == "输入答案"
    ).set_value("4").run()
    next(
        button for button in at.button if button.label == "提交答案"
    ).click().run()

    assert not at.exception
    captions = " ".join(item.value for item in at.caption)
    assert "REMSJ · 提取条件" in captions
    assert "找出关键条件" in captions
