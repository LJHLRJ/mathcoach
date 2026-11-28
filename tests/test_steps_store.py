"""步骤信号库：写入、读取、结算、脱敏与路径覆盖。"""
from datetime import datetime, timezone

from mathcoach.steps import StepAttempt, StepRun, StepStore, StepVerdict
from mathcoach.steps.store import step_db_path

NOW = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)


def _run(identifier: str = "run-1") -> StepRun:
    """构造一条最小步骤运行。"""
    return StepRun(
        id=identifier,
        exercise_id="hs-trig-002-e2",
        card_id="hs-trig-002",
        kc_ids=("kc-hs-trig-002-f1", "kc-hs-trig-002-p1"),
        step_count=2,
        created_at=NOW,
        updated_at=NOW,
    )


def _attempt(
    run_id: str, index: int, verdict: StepVerdict, answer: str
) -> StepAttempt:
    """构造一条步骤作答。"""
    return StepAttempt(
        run_id=run_id,
        exercise_id="hs-trig-002-e2",
        step_index=index,
        input=answer,
        verdict=verdict,
        expected="16/25" if index == 1 else "4/5",
        kc_id=(
            "kc-hs-trig-002-f1" if index == 1 else "kc-hs-trig-002-p1"
        ),
        created_at=NOW,
    )


def test_store_records_run_and_attempts(tmp_path) -> None:
    """运行与逐步作答可写入并按序号读取。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    try:
        store.save_run(_run())
        store.add_attempt(
            _attempt("run-1", 1, StepVerdict.CORRECT, "16/25")
        )
        store.add_attempt(
            _attempt("run-1", 2, StepVerdict.INCORRECT, "-4/5")
        )
        run = store.get_run("run-1")

        assert run is not None
        assert run.exercise_id == "hs-trig-002-e2"
        assert run.kc_ids == (
            "kc-hs-trig-002-f1",
            "kc-hs-trig-002-p1",
        )
        assert [item.step_index for item in run.attempts] == [1, 2]
        assert run.attempts[1].verdict is StepVerdict.INCORRECT
    finally:
        store.close()


def test_store_finalizes_and_lists_run(tmp_path) -> None:
    """结算后记录失败步骤与最终答案。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    try:
        store.save_run(_run())
        store.finalize_run(
            "run-1",
            final_answer="4/5",
            final_correct=False,
            failed_step_index=2,
            mismatch=False,
            kc_applied=True,
            missing_steps=(2,),
            now=NOW,
        )
        runs = store.list_runs()

        assert len(runs) == 1
        assert runs[0].failed_step_index == 2
        assert runs[0].missing_steps == (2,)
        assert runs[0].final_correct is False
        assert runs[0].kc_applied is True
        assert runs[0].step_count == 2
    finally:
        store.close()


def test_store_marks_abandoned_run(tmp_path) -> None:
    """放弃的步骤运行会保留放弃标记。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    try:
        store.save_run(_run())
        store.finalize_run(
            "run-1",
            final_answer="",
            final_correct=None,
            failed_step_index=None,
            mismatch=False,
            kc_applied=True,
            missing_steps=(2,),
            abandoned=True,
            now=NOW,
        )
        run = store.get_run("run-1")

        assert run is not None
        assert run.abandoned is True
        assert run.missing_steps == (2,)
        assert run.final_correct is None
    finally:
        store.close()


def test_store_sanitizes_answer(tmp_path) -> None:
    """学生输入中的手机号会脱敏后再落库。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    try:
        store.save_run(_run())
        store.add_attempt(
            _attempt("run-1", 1, StepVerdict.INCORRECT, "我的电话 13800138000")
        )
        run = store.get_run("run-1")

        assert run is not None
        assert "13800138000" not in run.attempts[0].input
        assert "[已脱敏]" in run.attempts[0].input
    finally:
        store.close()


def test_step_db_path_can_be_overridden(tmp_path, monkeypatch) -> None:
    """步骤库路径可用环境变量覆盖。"""
    target = tmp_path / "signals.sqlite3"
    monkeypatch.setenv("MATHCOACH_STEP_DB", str(target))

    assert step_db_path() == target
