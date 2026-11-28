"""分步板书 UI：步骤区展示当前帧文字，并可从该步发起追问。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _click(at: AppTest, label: str) -> None:
    """按按钮文本点击并重跑。"""
    next(button for button in at.button if label in button.label).click().run()
    assert not at.exception


def _open_quiz(at: AppTest, card_id: str, goal: str) -> None:
    """选择卡片并进入小测第一题。"""
    at.selectbox[0].select(card_id).run()
    assert not at.exception
    at.text_input[0].set_value(goal)
    _click(at, "确认目标")
    _click(at, "开始小测")


def test_wave_board_frame_renders_in_step_guide(tmp_path, monkeypatch) -> None:
    """振幅题第一步展示波形帧与文字说明。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15).run()
    _open_quiz(at, "hs-trig-004", "搞懂正弦型函数")

    captions = " ".join(item.value for item in at.caption)
    markdown = " ".join(item.value for item in at.markdown)
    assert "板书 · 第 1 步：先读出 ω" in captions
    assert "x 前的系数就是 ω=2" in markdown
    assert any("针对这一步提问" in button.label for button in at.button)


def test_cosine_board_frame_renders_in_step_guide(tmp_path, monkeypatch) -> None:
    """余弦定理题第一步展示三角形帧。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15).run()
    _open_quiz(at, "hs-trig-005", "搞懂余弦定理")

    captions = " ".join(item.value for item in at.caption)
    markdown = " ".join(item.value for item in at.markdown)
    assert "板书 · 第 1 步：先看夹角项" in captions
    assert "2ab cos C 前面是减号" in markdown
