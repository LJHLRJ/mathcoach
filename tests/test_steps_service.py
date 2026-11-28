"""步骤运行编排：KC 观测、首个失败步骤、匹配异常与游客模式。"""
from mathcoach.domain.bkt import initial_mastery
from mathcoach.steps import STEP_SPECS, StepRecorder, StepStore, StepVerdict
from mathcoach.steps.models import StepRun, observations_for
from mathcoach.tutor.mastery_store import KCMasteryStore

SPECS = STEP_SPECS["hs-trig-002-e2"]


def test_recorder_applies_kc_observations(tmp_path) -> None:
    """正确步骤与失败步骤分别写入对应 KC 的影子掌握度。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    kc_store = KCMasteryStore(tmp_path / "kc.sqlite3")
    recorder = StepRecorder(store=store, kc_store=kc_store)
    try:
        run_id = recorder.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        recorder.record(run_id, SPECS[0], "16/25")
        recorder.record(run_id, SPECS[1], "-4/5")
        run = recorder.finalize(
            run_id, final_answer="-4/5", final_correct=False
        )

        assert run is not None
        assert run.failed_step_index == 2
        assert run.mismatch is False
        assert run.kc_applied is True
        assert kc_store.get("kc-hs-trig-002-f1") > initial_mastery()
        assert kc_store.get("kc-hs-trig-002-p1") < initial_mastery()
    finally:
        recorder.close()


def test_finalize_is_idempotent(tmp_path) -> None:
    """重复结算不会重复写 KC 观测。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    kc_store = KCMasteryStore(tmp_path / "kc.sqlite3")
    recorder = StepRecorder(store=store, kc_store=kc_store)
    try:
        run_id = recorder.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        recorder.record(run_id, SPECS[0], "16/25")
        recorder.finalize(run_id, final_answer="4/5", final_correct=True)
        first = kc_store.sample_size("kc-hs-trig-002-f1")

        recorder.finalize(run_id, final_answer="4/5", final_correct=True)

        assert kc_store.sample_size("kc-hs-trig-002-f1") == first
    finally:
        recorder.close()


def test_all_steps_correct_but_final_wrong_is_mismatch(tmp_path) -> None:
    """步骤全对但最终答案错误时记录 mismatch 信号。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    recorder = StepRecorder(store=store)
    try:
        run_id = recorder.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        recorder.record(run_id, SPECS[0], "16/25")
        recorder.record(run_id, SPECS[1], "4/5")
        run = recorder.finalize(
            run_id, final_answer="3/5", final_correct=False
        )

        assert run is not None
        assert run.mismatch is True
        assert run.failed_step_index is None
    finally:
        recorder.close()


def test_observations_stop_after_first_failure() -> None:
    """失败步骤之后的步骤不再归因。"""
    from mathcoach.steps import StepAttempt

    run = StepRun(
        exercise_id="hs-trig-002-e2",
        card_id="hs-trig-002",
        attempts=(
            StepAttempt(
                run_id="r",
                exercise_id="hs-trig-002-e2",
                step_index=1,
                input="9/25",
                verdict=StepVerdict.INCORRECT,
                expected="16/25",
                kc_id="kc-hs-trig-002-f1",
            ),
            StepAttempt(
                run_id="r",
                exercise_id="hs-trig-002-e2",
                step_index=2,
                input="4/5",
                verdict=StepVerdict.CORRECT,
                expected="4/5",
                kc_id="kc-hs-trig-002-p1",
            ),
        ),
    )

    observations = observations_for(run)

    assert [(item.kc_id, item.correct) for item in observations] == [
        ("kc-hs-trig-002-f1", False)
    ]


def test_disabled_recorder_does_not_persist(tmp_path) -> None:
    """游客模式仍给判定，但不写步骤库。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    recorder = StepRecorder(store=store, enabled=False)
    try:
        run_id = recorder.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        attempt = recorder.record(run_id, SPECS[0], "16/25")
        run = recorder.finalize(
            run_id, final_answer="4/5", final_correct=True
        )

        assert run_id == ""
        assert attempt.verdict is StepVerdict.CORRECT
        assert run is None
        assert store.list_runs() == []
    finally:
        recorder.close()


def test_fast_step_gets_higher_gain_than_slow_step(tmp_path) -> None:
    """同样答对，快速完成比慢速完成获得更高的 KC 增益。"""
    fast_store = StepStore(tmp_path / "fast-steps.sqlite3")
    fast_kc = KCMasteryStore(tmp_path / "fast-kc.sqlite3")
    fast = StepRecorder(store=fast_store, kc_store=fast_kc)
    slow_store = StepStore(tmp_path / "slow-steps.sqlite3")
    slow_kc = KCMasteryStore(tmp_path / "slow-kc.sqlite3")
    slow = StepRecorder(store=slow_store, kc_store=slow_kc)
    try:
        fast_id = fast.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        fast.record(fast_id, SPECS[0], "16/25", elapsed_s=10.0)
        fast.finalize(
            fast_id, final_answer="4/5", final_correct=True
        )
        slow_id = slow.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        slow.record(slow_id, SPECS[0], "16/25", elapsed_s=999.0)
        slow.finalize(
            slow_id, final_answer="4/5", final_correct=True
        )

        assert fast_kc.get("kc-hs-trig-002-f1") > slow_kc.get(
            "kc-hs-trig-002-f1"
        )
    finally:
        fast.close()
        slow.close()


def test_missing_steps_are_recorded(tmp_path) -> None:
    """只完成部分步骤时记录缺失序号。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    recorder = StepRecorder(store=store)
    try:
        run_id = recorder.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        recorder.record(run_id, SPECS[0], "16/25", elapsed_s=10.0)
        run = recorder.finalize(
            run_id, final_answer="4/5", final_correct=True
        )

        assert run is not None
        assert run.missing_steps == (2,)
        assert run.mismatch is False
    finally:
        recorder.close()


def test_missing_before_weakens_later_correct_step(tmp_path) -> None:
    """跳过前置步骤后，后续步骤答对的 KC 增益更弱。"""
    specs = STEP_SPECS["hs-trig-002-e3"]
    full_store = StepStore(tmp_path / "full-steps.sqlite3")
    full_kc = KCMasteryStore(tmp_path / "full-kc.sqlite3")
    full = StepRecorder(store=full_store, kc_store=full_kc)
    partial_store = StepStore(tmp_path / "partial-steps.sqlite3")
    partial_kc = KCMasteryStore(tmp_path / "partial-kc.sqlite3")
    partial = StepRecorder(store=partial_store, kc_store=partial_kc)
    try:
        full_id = full.start("hs-trig-002-e3", "hs-trig-002", specs)
        full.record(full_id, specs[0], "同角平方关系", elapsed_s=5.0)
        full.record(full_id, specs[1], "1", elapsed_s=5.0)
        full.finalize(
            full_id, final_answer="1", final_correct=True
        )
        partial_id = partial.start(
            "hs-trig-002-e3", "hs-trig-002", specs
        )
        partial.record(partial_id, specs[1], "1", elapsed_s=5.0)
        partial.finalize(
            partial_id, final_answer="1", final_correct=True
        )

        assert full_kc.get("kc-hs-trig-002-f1") > partial_kc.get(
            "kc-hs-trig-002-f1"
        )
    finally:
        full.close()
        partial.close()


def test_abandon_applies_observations_once(tmp_path) -> None:
    """放弃的步骤运行会应用一次影子观测，且不重复更新。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    kc_store = KCMasteryStore(tmp_path / "kc.sqlite3")
    recorder = StepRecorder(store=store, kc_store=kc_store)
    try:
        run_id = recorder.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        recorder.record(run_id, SPECS[0], "16/25", elapsed_s=10.0)
        run = recorder.abandon(run_id)

        assert run is not None
        assert run.abandoned is True
        assert run.kc_applied is True
        assert run.missing_steps == (2,)
        assert kc_store.sample_size("kc-hs-trig-002-f1") == 1

        recorder.abandon(run_id)
        assert kc_store.sample_size("kc-hs-trig-002-f1") == 1
    finally:
        recorder.close()


def test_starting_new_run_abandons_previous(tmp_path) -> None:
    """同一题开始新步骤运行前，旧运行会被标记为放弃。"""
    store = StepStore(tmp_path / "steps.sqlite3")
    recorder = StepRecorder(store=store)
    try:
        first_id = recorder.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        recorder.record(first_id, SPECS[0], "16/25", elapsed_s=10.0)

        second_id = recorder.start("hs-trig-002-e2", "hs-trig-002", SPECS)
        first = store.get_run(first_id)
        second = store.get_run(second_id)

        assert first is not None and first.abandoned is True
        assert second is not None and second.abandoned is False
    finally:
        recorder.close()
