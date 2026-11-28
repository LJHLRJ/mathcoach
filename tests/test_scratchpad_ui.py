"""草稿原位标注：步骤判定贴在该行，并可展开原因。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _open_quiz(at: AppTest, card_id: str, goal: str) -> None:
    at.selectbox[0].select(card_id).run()
    at.text_input[0].set_value(goal)
    next(
        button for button in at.button if button.label == "确认目标"
    ).click().run()
    next(
        button for button in at.button if button.label == "开始小测"
    ).click().run()
    assert not at.exception


def _check_first_step(at: AppTest, answer: str) -> None:
    next(
        box for box in at.text_input if box.label == "这一步的结果"
    ).set_value(answer).run()
    next(
        button for button in at.button if button.label == "检查这一步"
    ).click().run()
    assert not at.exception


def test_correct_step_shows_inline_marker_and_reason(
    tmp_path, monkeypatch
) -> None:
    """答对时原位显示正确徽标，并可展开原因。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    monkeypatch.setenv(
        "MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3")
    )
    monkeypatch.setenv("MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3"))

    at = AppTest.from_file(APP_PATH, default_timeout=20).run()
    _open_quiz(at, "hs-trig-004", "搞懂正弦型函数")
    _check_first_step(at, "2")

    assert any("正确" in item.value for item in at.success)
    assert any(
        "为什么这样判定？" in expander.label
        for expander in at.expander
    )
    assert any(
        "你的输入：2" in item.value for item in at.caption
    )


def test_incorrect_step_shows_reason_and_kc_visual(
    tmp_path, monkeypatch
) -> None:
    """答错时原位显示错误徽标、原因与对应 KC 动态讲解。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    monkeypatch.setenv(
        "MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3")
    )
    monkeypatch.setenv("MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3"))

    at = AppTest.from_file(APP_PATH, default_timeout=20).run()
    _open_quiz(at, "hs-trig-004", "搞懂正弦型函数")
    _check_first_step(at, "3")

    assert any("这一步不对" in item.value for item in at.error)
    labels = {expander.label for expander in at.expander}
    assert "为什么这样判定？" in labels
    assert "动态讲解：振幅与周期公式" in labels
    assert any("公式记错" in item.value for item in at.markdown)
