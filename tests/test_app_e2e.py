"""端到端 AppTest：讲解 → 小测 → 收据 → L6 复述 → 结算 → 仪表盘 → 周报 → 重启持久化。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _click(at, label: str) -> None:
    """点击唯一匹配的按钮并运行。"""
    next(button for button in at.button if button.label == label).click().run()


def test_full_learning_loop_end_to_end(tmp_path, monkeypatch):
    path = tmp_path / "e2e.sqlite3"
    monkeypatch.setenv("MATHCOACH_DB", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    assert not at.exception

    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数")
    _click(at, "确认目标")
    _click(at, "开始小测")

    at.radio[0].set_value("y² = x")
    _click(at, "提交答案")
    _click(at, "再试一次")
    at.radio[0].set_value("y = x²")
    _click(at, "提交答案")
    assert not at.exception
    assert any("收据已生成" in subheader.value for subheader in at.subheader)

    at.text_area[0].set_value("每个 x 只有唯一 y 与之对应")
    _click(at, "提交复述")
    assert any("L6 复述质量：完整" in caption.value for caption in at.caption)

    _click(at, "继续")
    at.radio[0].set_value("x ≥ 2")
    _click(at, "提交答案")
    _click(at, "继续")
    at.radio[0].set_value("7")
    _click(at, "提交答案")
    _click(at, "继续")

    assert not at.exception
    assert any("本次闭环完成" in subheader.value for subheader in at.subheader)

    at.selectbox[1].select("仪表盘").run()
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["收据总数"] == "3"

    at.selectbox[1].select("周报").run()
    assert any("掌握度变化" in markdown.value for markdown in at.markdown)
    assert any(
        "hs-function-intro-001" in markdown.value and "→" in markdown.value
        for markdown in at.markdown
    )

    second = AppTest.from_file(APP_PATH, default_timeout=15)
    second.run()
    assert not second.exception
    second.session_state["main_tabs"] = "错题本"
    second.run()
    captions = " ".join(caption.value for caption in second.caption)
    assert "你的答案：y² = x" in captions
