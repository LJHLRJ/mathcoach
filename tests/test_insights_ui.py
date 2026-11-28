"""步骤卡点 UI：本机历史反复出错时展示提示与追问锚点。"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.steps import StepAttempt, StepRun, StepStore, StepVerdict

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
NOW = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)


def _seed_runs(path: Path) -> None:
    """写入三次步骤运行，第一步错两次。"""
    store = StepStore(path)
    try:
        for index, verdict in enumerate(
            (StepVerdict.INCORRECT, StepVerdict.CORRECT, StepVerdict.INCORRECT)
        ):
            run = StepRun(
                id=f"run-{index}",
                exercise_id="hs-trig-002-e1",
                card_id="hs-trig-002",
                step_count=2,
                created_at=NOW + timedelta(minutes=index),
            )
            store.save_run(run)
            store.add_attempt(
                StepAttempt(
                    run_id=run.id,
                    exercise_id="hs-trig-002-e1",
                    step_index=1,
                    input="1",
                    verdict=verdict,
                    expected="1",
                    kc_id="kc-hs-trig-002-f1",
                    step_tag="identity",
                )
            )
    finally:
        store.close()


def test_step_insight_shows_local_stuck_step(tmp_path, monkeypatch) -> None:
    """本机三次运行中同一步错两次时展示卡点。"""
    step_path = tmp_path / "steps.sqlite3"
    _seed_runs(step_path)
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv("MATHCOACH_STEP_DB", str(step_path))
    monkeypatch.setenv(
        "MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=20).run()
    at.selectbox[0].select("hs-trig-002").run()
    at.text_input[0].set_value("搞懂同角关系")
    next(
        button for button in at.button if button.label == "确认目标"
    ).click().run()
    next(
        button for button in at.button if button.label == "开始小测"
    ).click().run()

    assert not at.exception
    captions = " ".join(item.value for item in at.caption)
    assert "近期卡点" in captions
    assert "第 1 步错了 2 次" in captions
    assert any(
        button.label == "针对这一步提问" for button in at.button
    )
