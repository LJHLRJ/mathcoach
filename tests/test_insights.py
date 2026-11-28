"""步骤卡点聚合：窗口、阈值与排序。"""
from datetime import datetime, timedelta, timezone

from mathcoach.insights import build_step_insights
from mathcoach.steps.models import StepAttempt, StepRun, StepVerdict

NOW = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)


def _run(
    index: int,
    *,
    exercise_id: str = "ex-1",
    verdicts: tuple[int, StepVerdict] | None = None,
) -> StepRun:
    """构造一条只含单个失败步骤的运行。"""
    attempts = ()
    if verdicts is not None:
        step_index, verdict = verdicts
        attempts = (
            StepAttempt(
                run_id=f"run-{index}",
                exercise_id=exercise_id,
                step_index=step_index,
                input="x",
                verdict=verdict,
                expected="y",
                kc_id="kc-1",
                step_tag="formula",
            ),
        )
    return StepRun(
        id=f"run-{index}",
        exercise_id=exercise_id,
        card_id="card-a",
        step_count=3,
        attempts=attempts,
        created_at=NOW + timedelta(minutes=index),
    )


def test_insight_appears_after_two_failures_in_three_runs() -> None:
    """最近三次中同一步骤错两次即展示。"""
    runs = [
        _run(0, verdicts=(2, StepVerdict.INCORRECT)),
        _run(1, verdicts=(2, StepVerdict.CORRECT)),
        _run(2, verdicts=(2, StepVerdict.INCORRECT)),
    ]

    insights = build_step_insights(runs, "ex-1")

    assert len(insights) == 1
    assert insights[0].step_index == 2
    assert insights[0].fail_count == 2
    assert insights[0].run_count == 3


def test_insight_requires_minimum_runs() -> None:
    """不足三次运行时不展示。"""
    runs = [
        _run(0, verdicts=(2, StepVerdict.INCORRECT)),
        _run(1, verdicts=(2, StepVerdict.INCORRECT)),
    ]

    assert build_step_insights(runs, "ex-1") == ()


def test_insight_requires_repeated_failure() -> None:
    """同一步骤只错一次时不展示。"""
    runs = [
        _run(0, verdicts=(1, StepVerdict.INCORRECT)),
        _run(1, verdicts=(2, StepVerdict.INCORRECT)),
        _run(2, verdicts=(3, StepVerdict.INCORRECT)),
    ]

    assert build_step_insights(runs, "ex-1") == ()


def test_insights_are_sorted_by_failures_then_step() -> None:
    """多次失败排在前面，其次按步骤序号。"""
    runs = [
        _run(0, verdicts=(3, StepVerdict.INCORRECT)),
        _run(1, verdicts=(3, StepVerdict.INCORRECT)),
        _run(2, verdicts=(2, StepVerdict.INCORRECT)),
    ]
    runs.append(
        StepRun(
            id="run-3",
            exercise_id="ex-1",
            card_id="card-a",
            step_count=3,
            attempts=(
                StepAttempt(
                    run_id="run-3",
                    exercise_id="ex-1",
                    step_index=2,
                    input="x",
                    verdict=StepVerdict.INCORRECT,
                    expected="y",
                    step_tag="formula",
                ),
                StepAttempt(
                    run_id="run-3",
                    exercise_id="ex-1",
                    step_index=3,
                    input="x",
                    verdict=StepVerdict.INCORRECT,
                    expected="y",
                    step_tag="formula",
                ),
            ),
            created_at=NOW + timedelta(minutes=3),
        )
    )

    insights = build_step_insights(runs, "ex-1", window=4)

    assert [item.step_index for item in insights] == [3, 2]


def test_other_exercise_runs_are_ignored() -> None:
    """其他题目的运行不参与聚合。"""
    runs = [
        _run(0, exercise_id="ex-2", verdicts=(2, StepVerdict.INCORRECT)),
        _run(1, exercise_id="ex-2", verdicts=(2, StepVerdict.INCORRECT)),
        _run(2, exercise_id="ex-2", verdicts=(2, StepVerdict.INCORRECT)),
    ]

    assert build_step_insights(runs, "ex-1") == ()
