"""KC 动态讲解：知识点浏览、答错步骤入口与降级。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _open_knowledge_page(at: AppTest, card_id: str) -> None:
    """选择卡片、确认目标并打开知识点浏览。"""
    at.selectbox[0].select(card_id).run()
    at.text_input[0].set_value("搞懂这个知识点")
    next(
        button for button in at.button if button.label == "确认目标"
    ).click().run()
    next(
        button for button in at.button if button.label == "先学习此知识点"
    ).click().run()


def test_knowledge_browser_shows_kc_dynamic_visual(
    tmp_path, monkeypatch
) -> None:
    """知识点浏览页展示 KC 动态讲解与交互滑块。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "kc-visual.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()

    _open_knowledge_page(at, "hs-trig-002")

    assert not at.exception
    values = [markdown.value for markdown in at.markdown]
    assert "**KC 动态讲解**" in values
    assert any(
        expander.label == "动态讲解：象限符号判定"
        for expander in at.expander
    )
    assert any(slider.label == "角 x（度）" for slider in at.slider)


def test_card_without_kc_visual_hides_section(
    tmp_path, monkeypatch
) -> None:
    """没有登记动态讲解的卡片不显示该区块。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "kc-visual-empty.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()

    _open_knowledge_page(at, "hs-function-intro-001")

    assert not at.exception
    values = [markdown.value for markdown in at.markdown]
    assert "**KC 动态讲解**" not in values


def test_wrong_step_offers_kc_dynamic_visual(
    tmp_path, monkeypatch
) -> None:
    """步骤答错时就地提供对应 KC 的动态讲解。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "kc-visual-step.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()

    at.selectbox[0].select("hs-trig-002").run()
    at.text_input[0].set_value("搞懂同角关系")
    next(
        button for button in at.button if button.label == "确认目标"
    ).click().run()
    next(
        button for button in at.button if button.label == "开始小测"
    ).click().run()
    next(
        radio for radio in at.radio if radio.label == "选择答案"
    ).set_value("sin²x+cos²x=1").run()
    next(
        button for button in at.button if button.label == "提交答案"
    ).click().run()
    next(
        button for button in at.button if button.label == "继续"
    ).click().run()

    step_boxes = [
        box for box in at.text_input if box.label == "这一步的结果"
    ]
    step_boxes[1].set_value("-4/5").run()
    next(
        button
        for button in at.button
        if button.label == "检查这一步" and not button.disabled
    ).click().run()

    assert not at.exception
    assert any(
        expander.label == "动态讲解：象限符号判定"
        for expander in at.expander
    )


def test_kc_visual_failure_does_not_block_page(
    tmp_path, monkeypatch
) -> None:
    """动态讲解渲染失败时只提示，不影响知识点浏览。"""
    import mathcoach.ui.visuals.quadrant_sign as quadrant

    def boom() -> None:
        """模拟渲染崩溃。"""
        raise RuntimeError("boom")

    monkeypatch.setattr(quadrant, "render", boom)
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "kc-visual-fail.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()

    _open_knowledge_page(at, "hs-trig-002")

    assert not at.exception
    assert any(
        "动态讲解暂不可用" in info.value for info in at.info
    )
    assert any(
        button.label == "开始练习此知识点" for button in at.button
    )
