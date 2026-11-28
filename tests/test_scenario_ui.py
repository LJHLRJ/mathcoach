"""讲解页情境探索：参数滑块与边界提示。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _click(at: AppTest, label: str) -> None:
    next(button for button in at.button if label in button.label).click().run()
    assert not at.exception


def _open_explain(at: AppTest, card_id: str, goal: str) -> None:
    at.selectbox[0].select(card_id).run()
    assert not at.exception
    at.text_input[0].set_value(goal)
    _click(at, "确认目标")


def test_tangent_scenario_renders_in_explain(tmp_path, monkeypatch) -> None:
    """导数卡讲解页出现切点滑块与不计入掌握度提示。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15).run()
    _open_explain(at, "hs-func-004", "搞懂导数的几何意义")

    labels = [slider.label for slider in at.slider]
    captions = " ".join(item.value for item in at.caption)
    infos = " ".join(item.value for item in at.info)
    assert "切点 x0" in labels
    assert "情境探索不计入掌握度" in captions, infos
    assert "切线斜率" in captions


def test_vector_scenario_renders_in_explain(tmp_path, monkeypatch) -> None:
    """向量卡讲解页出现四个分量滑块。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15).run()
    _open_explain(at, "hs-vector-002", "搞懂向量加减法")

    labels = [slider.label for slider in at.slider]
    assert {
        "a 的 x 分量",
        "a 的 y 分量",
        "b 的 x 分量",
        "b 的 y 分量",
    } <= set(labels)
