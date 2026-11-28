"""分步填写 UI：步骤判定、最终答案结算与失步记录。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.steps import StepStore, StepVerdict

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _start_trig_card(at: AppTest) -> None:
    """选择同角关系卡并进入小测第一题。"""
    at.selectbox[0].select("hs-trig-002").run()
    at.text_input[0].set_value("搞懂同角关系")
    next(
        button for button in at.button if button.label == "确认目标"
    ).click().run()
    next(
        button for button in at.button if button.label == "开始小测"
    ).click().run()


def _advance_to_e2(at: AppTest) -> None:
    """答对 e1 后进入第二题。"""
    next(
        radio for radio in at.radio if radio.label == "选择答案"
    ).set_value("sin²x+cos²x=1").run()
    next(
        button for button in at.button if button.label == "提交答案"
    ).click().run()
    next(
        button for button in at.button if button.label == "继续"
    ).click().run()


def test_step_guide_records_attempts_and_finalizes(tmp_path, monkeypatch) -> None:
    """两步作答、失败步骤与最终答案都写入步骤库。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv("MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3"))
    monkeypatch.setenv("MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3"))

    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    _start_trig_card(at)
    _advance_to_e2(at)

    assert not at.exception
    assert any(
        expander.label == "分步填写（可选）"
        for expander in at.expander
    )

    step_inputs = [
        box for box in at.text_input if box.label == "这一步的结果"
    ]
    step_inputs[0].set_value("16/25").run()
    next(
        button for button in at.button if button.label == "检查这一步"
    ).click().run()

    assert not at.exception
    step_inputs = [
        box for box in at.text_input if box.label == "这一步的结果"
    ]
    step_inputs[0].set_value("-4/5").run()
    next(
        button for button in at.button if button.label == "检查这一步"
    ).click().run()

    next(
        box for box in at.text_input if box.label == "输入答案"
    ).set_value("-4/5").run()
    next(
        button for button in at.button if button.label == "提交答案"
    ).click().run()

    assert not at.exception
    store = StepStore(tmp_path / "steps.sqlite3")
    try:
        runs = store.list_runs()
    finally:
        store.close()
    assert len(runs) == 1
    assert runs[0].failed_step_index == 2
    assert runs[0].final_correct is False
    assert [item.verdict for item in runs[0].attempts] == [
        StepVerdict.CORRECT,
        StepVerdict.INCORRECT,
    ]
    assert all(
        item.elapsed_s is not None for item in runs[0].attempts
    )


def test_switching_card_abandons_unfinished_steps(
    tmp_path, monkeypatch
) -> None:
    """切换卡片时把未结算的步骤运行标记为放弃。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv("MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3"))
    monkeypatch.setenv("MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3"))

    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    _start_trig_card(at)

    next(
        box for box in at.text_input if box.label == "这一步的结果"
    ).set_value("1").run()
    next(
        button for button in at.button if button.label == "检查这一步"
    ).click().run()
    at.selectbox[0].select("hs-trig-001").run()

    assert not at.exception
    store = StepStore(tmp_path / "steps.sqlite3")
    try:
        runs = store.list_runs()
    finally:
        store.close()
    assert len(runs) == 1
    assert runs[0].abandoned is True
    assert runs[0].final_answer == ""
    assert runs[0].kc_applied is True
