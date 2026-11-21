"""可视化接入学习流程：已知卡渲染，失败显示提示且不阻断。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _start_tangent_card(at) -> None:
    at.selectbox[0].select("hs-func-004").run()
    at.text_input[0].set_value("搞懂切线")
    at.button[0].click().run()


def test_known_card_renders_without_blocking(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    _start_tangent_card(at)

    assert not at.exception
    assert not any("可视化暂不可用" in info.value for info in at.info)


def test_visual_failure_shows_message_and_continues(tmp_path, monkeypatch):
    import mathcoach.ui.visuals.tangent as tangent

    def boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(tangent, "render", boom)
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    _start_tangent_card(at)

    assert not at.exception
    assert any("可视化暂不可用" in info.value for info in at.info)
    # 学习流程仍停在讲解页，可继续开始小测
    assert at.button[0].label == "开始小测"
