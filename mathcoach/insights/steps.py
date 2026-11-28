"""步骤卡点聚合：只统计本机历史，不做跨用户比较。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..steps.models import StepRun, StepVerdict

DEFAULT_WINDOW = 3
DEFAULT_MIN_RUNS = 3
DEFAULT_MIN_FAILURES = 2


@dataclass(frozen=True)
class StepInsight:
    """一道题上的一个反复出错步骤。

    Attributes:
        exercise_id: 题目 ID。
        step_index: 步骤序号。
        step_tag: 步骤标签，可为空。
        fail_count: 最近窗口中出错次数。
        run_count: 最近窗口内的有效运行次数。
    """

    exercise_id: str
    step_index: int
    step_tag: str
    fail_count: int
    run_count: int


def build_step_insights(
    runs: Sequence[StepRun],
    exercise_id: str,
    *,
    window: int = DEFAULT_WINDOW,
    min_runs: int = DEFAULT_MIN_RUNS,
    min_failures: int = DEFAULT_MIN_FAILURES,
) -> tuple[StepInsight, ...]:
    """从最近几次步骤运行中找出反复出错的步骤。

    Args:
        runs: 步骤运行记录。
        exercise_id: 当前题目。
        window: 只统计最近几次运行。
        min_runs: 至少需要几次有效运行才展示。
        min_failures: 同一步骤至少错几次才展示。

    Returns:
        按出错次数降序、步骤序号升序排列的洞察；样本不足时为空。
    """
    selected = [
        run
        for run in runs
        if run.exercise_id == exercise_id and run.attempts
    ]
    selected.sort(key=lambda item: item.created_at)
    recent = selected[-max(1, int(window)):]
    if len(recent) < max(1, int(min_runs)):
        return ()
    counts: dict[tuple[int, str], int] = {}
    for run in recent:
        failed = {
            (attempt.step_index, attempt.step_tag)
            for attempt in run.attempts
            if attempt.verdict is StepVerdict.INCORRECT
        }
        for key in failed:
            counts[key] = counts.get(key, 0) + 1
    insights = [
        StepInsight(
            exercise_id=exercise_id,
            step_index=step_index,
            step_tag=step_tag,
            fail_count=count,
            run_count=len(recent),
        )
        for (step_index, step_tag), count in counts.items()
        if count >= max(1, int(min_failures))
    ]
    insights.sort(key=lambda item: (-item.fail_count, item.step_index))
    return tuple(insights)
