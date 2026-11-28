"""路径检验 UI：收据后先验证检查点，再揭示路径。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _click(at: AppTest, label: str) -> None:
    """按按钮文本点击并重跑。"""
    next(button for button in at.button if button.label == label).click().run()
    assert not at.exception


def _open_receipt_e2(at: AppTest) -> None:
    """进入同角关系卡第二题并答对。"""
    at.selectbox[0].select("hs-trig-002").run()
    at.text_input[0].set_value("搞懂同角关系")
    _click(at, "确认目标")
    _click(at, "开始小测")
    next(
        radio for radio in at.radio if radio.label == "选择答案"
    ).set_value("sin²x+cos²x=1").run()
    _click(at, "提交答案")
    _click(at, "继续")
    next(
        box for box in at.text_input if box.label == "输入答案"
    ).set_value("4/5")
    _click(at, "提交答案")


def test_strategy_probe_reveals_path_after_checkpoints(
    tmp_path, monkeypatch
) -> None:
    """检查点通过后才显示路径名称与总结。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_DIALOG_DB", str(tmp_path / "dialog.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=20).run()
    _open_receipt_e2(at)

    assert any(
        expander.label == "还有没有别的方法？"
        for expander in at.expander
    )
    markdown = " ".join(item.value for item in at.markdown)
    assert "另一种思路" in markdown
    assert "直角三角形法" not in markdown

    next(
        box for box in at.text_input if box.label == "这一步的结果"
    ).set_value("4").run()
    _click(at, "验证这一步")

    next(
        box for box in at.text_input if box.label == "这一步的结果"
    ).set_value("4/5").run()
    _click(at, "验证这一步")

    success = " ".join(item.value for item in at.success)
    markdown = " ".join(item.value for item in at.markdown)
    assert "路径成立：直角三角形法" in success
    assert "邻边为 4" in markdown


def test_receipt_without_path_has_no_probe(tmp_path, monkeypatch) -> None:
    """未登记路径的题目不显示多解入口。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=20).run()
    at.selectbox[0].select("hs-trig-002").run()
    at.text_input[0].set_value("搞懂同角关系")
    _click(at, "确认目标")
    _click(at, "开始小测")
    next(
        radio for radio in at.radio if radio.label == "选择答案"
    ).set_value("sin²x+cos²x=1").run()
    _click(at, "提交答案")

    assert not any(
        expander.label == "还有没有别的方法？"
        for expander in at.expander
    )
