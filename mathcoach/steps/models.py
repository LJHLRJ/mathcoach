"""步骤级错误定位：步骤元数据、判定结果与运行记录。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class StepVerdict(str, Enum):
    """单步判定的五种结论。"""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNVERIFIABLE = "unverifiable"
    REJECTED = "rejected"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class StepSpec:
    """一道题的一个可填写步骤。

    Attributes:
        exercise_id: 所属题目。
        index: 步骤序号，从 1 开始。
        prompt: 该步的问题文本。
        expected: 确定性代码给出的期望结果。
        variables: 表达式允许的变量。
        kc_id: 该步对应的知识点组件。
        step_tag: 步骤标签，如 identity / condition / sign。
        input_kind: expr / number / sign / order / pair。
        acceptable: 文字或符号类答案的可接受写法。
    """

    exercise_id: str
    index: int
    prompt: str
    expected: str
    variables: tuple[str, ...] = ()
    kc_id: str = ""
    step_tag: str = ""
    input_kind: str = "expr"
    acceptable: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepAttempt:
    """一次步骤作答及其判定。"""

    run_id: str
    exercise_id: str
    step_index: int
    input: str
    verdict: StepVerdict
    expected: str
    kc_id: str = ""
    step_tag: str = ""
    elapsed_s: float | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class StepRun:
    """一次分步作答的完整记录。"""

    exercise_id: str
    card_id: str
    kc_ids: tuple[str, ...] = ()
    mode: str = "guided"
    step_count: int = 0
    failed_step_index: int | None = None
    missing_steps: tuple[int, ...] = ()
    final_answer: str = ""
    final_correct: bool | None = None
    mismatch: bool = False
    abandoned: bool = False
    kc_applied: bool = False
    attempts: tuple[StepAttempt, ...] = ()
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class StepObservation:
    """一次步骤运行聚合出的 KC 级观测。"""

    kc_id: str
    correct: bool
    elapsed_s: float | None = None
    missing_before: bool = False


def observations_for(run: StepRun) -> tuple[StepObservation, ...]:
    """把步骤运行聚合成 KC 观测。

    首个 INCORRECT 步骤之前的正确步骤记为正观测；失败步骤本身记为负
    观测；失败之后的步骤不再归因。UNVERIFIABLE / REJECTED 不产生观测。
    ``elapsed_s`` 取该 KC 下最慢的一次；任一前置步骤缺失则
    ``missing_before`` 为真，供上层降低观测权重。
    """
    ordered = sorted(run.attempts, key=lambda item: item.step_index)
    present = {attempt.step_index for attempt in ordered}
    seen: dict[str, StepObservation] = {}
    for attempt in ordered:
        if not attempt.kc_id:
            continue
        missing_before = any(
            index not in present
            for index in range(1, attempt.step_index)
        )
        if attempt.verdict is StepVerdict.CORRECT:
            previous = seen.get(attempt.kc_id)
            if previous is None:
                seen[attempt.kc_id] = StepObservation(
                    kc_id=attempt.kc_id,
                    correct=True,
                    elapsed_s=attempt.elapsed_s,
                    missing_before=missing_before,
                )
            else:
                seen[attempt.kc_id] = StepObservation(
                    kc_id=attempt.kc_id,
                    correct=True,
                    elapsed_s=_slower(
                        previous.elapsed_s, attempt.elapsed_s
                    ),
                    missing_before=(
                        previous.missing_before or missing_before
                    ),
                )
        elif attempt.verdict is StepVerdict.INCORRECT:
            seen[attempt.kc_id] = StepObservation(
                kc_id=attempt.kc_id,
                correct=False,
                elapsed_s=attempt.elapsed_s,
                missing_before=missing_before,
            )
            break
    return tuple(seen.values())


def _slower(left: float | None, right: float | None) -> float | None:
    """合并同一 KC 的多步耗时；任一步未知则返回 None。"""
    if left is None or right is None:
        return None
    return max(left, right)
