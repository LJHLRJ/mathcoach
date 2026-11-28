"""AI 依赖度信号：只读历史收据、追问与步骤事件，输出提示供给建议。

纯函数，不读库、不读时钟、不调模型；不修改 BKT、FSRS 或收据独立程度。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Sequence

from .models import Receipt


class DependenceLevel(str, Enum):
    """依赖度信号等级；只有 ``TIGHTEN`` 会建议收紧主动提示。"""

    NONE = "none"
    WATCH = "watch"
    TIGHTEN = "tighten"


@dataclass(frozen=True)
class DependenceDialogEvent:
    """追问事件的只读快照，避免 domain 依赖 tutor 层。"""

    card_id: str
    level: int
    kind: str
    created_at: datetime


@dataclass(frozen=True)
class DependenceStepAttempt:
    """一次步骤作答的只读快照。"""

    step_index: int
    step_tag: str
    verdict: str


@dataclass(frozen=True)
class DependenceStepRun:
    """一次步骤运行的只读快照。"""

    exercise_id: str
    card_id: str
    created_at: datetime
    attempts: tuple[DependenceStepAttempt, ...] = ()


@dataclass(frozen=True)
class DependenceSignal:
    """一次依赖度判断。

    Attributes:
        level: 信号等级。
        card_id: 判断所在卡片。
        sample: 该卡片的历史收据数量。
        reasons: 命中的规则码，供上层映射展示文案。
        hint_ceiling: 建议的主动提示上限；None 表示不限制。
    """

    level: DependenceLevel
    card_id: str
    sample: int = 0
    reasons: tuple[str, ...] = ()
    hint_ceiling: int | None = None

    @property
    def tighten(self) -> bool:
        """是否建议收紧主动提示。"""
        return self.level is DependenceLevel.TIGHTEN


HINT_CEILING = 2
MIN_RECEIPTS = 3
WINDOW = 5
WATCH_SEMI = 2
TIGHTEN_SEMI = 3
MASTERY_FLOOR = 0.4
DIALOG_BASELINE_MIN = 5
DIALOG_RECENT = 3
DIALOG_DROP = 0.3
DIALOG_RECENT_MISSES = 2
STEP_WINDOW = 3
STEP_FAILURES = 2


def _ordered_receipts(
    card_id: str, receipts: Sequence[Receipt]
) -> list[Receipt]:
    """筛出同一卡片并按时间升序排列。"""
    selected = [item for item in receipts if item.card_id == card_id]
    return sorted(selected, key=lambda item: item.created_at)


def _dialog_score(event: DependenceDialogEvent) -> float | None:
    """把追问结果折算成 0–1 质量分；不可用事件返回 None。"""
    if event.kind == "hit":
        return 1.0
    if event.kind == "partial":
        return 0.5
    if event.kind == "miss":
        return 0.0
    return None


def _dialog_anomaly(
    card_id: str, events: Sequence[DependenceDialogEvent]
) -> bool:
    """判断最近追问命中率是否明显低于历史基线。"""
    scored = [
        event
        for event in events
        if event.card_id == card_id and _dialog_score(event) is not None
    ]
    scored.sort(key=lambda item: item.created_at)
    if len(scored) < DIALOG_BASELINE_MIN + DIALOG_RECENT:
        return False
    baseline = scored[:-DIALOG_RECENT]
    recent = scored[-DIALOG_RECENT:]
    baseline_rate = sum(_dialog_score(item) or 0.0 for item in baseline) / len(
        baseline
    )
    recent_rate = sum(_dialog_score(item) or 0.0 for item in recent) / len(
        recent
    )
    recent_misses = sum(1 for item in recent if item.kind == "miss")
    return (
        baseline_rate - recent_rate >= DIALOG_DROP
        and recent_misses >= DIALOG_RECENT_MISSES
    )


def _step_stuck(
    card_id: str, runs: Sequence[DependenceStepRun]
) -> bool:
    """判断同一题的同一步骤是否在最近几次运行中反复出错。"""
    by_exercise: dict[str, list[DependenceStepRun]] = {}
    for run in runs:
        if run.card_id != card_id or not run.attempts:
            continue
        by_exercise.setdefault(run.exercise_id, []).append(run)
    for items in by_exercise.values():
        recent = sorted(items, key=lambda item: item.created_at)[-STEP_WINDOW:]
        counts: dict[tuple[int, str], int] = {}
        for run in recent:
            failed = {
                (attempt.step_index, attempt.step_tag)
                for attempt in run.attempts
                if attempt.verdict == "incorrect"
            }
            for key in failed:
                counts[key] = counts.get(key, 0) + 1
        if any(count >= STEP_FAILURES for count in counts.values()):
            return True
    return False


def evaluate_dependence(
    card_id: str,
    receipts: Sequence[Receipt],
    *,
    dialog_events: Sequence[DependenceDialogEvent] = (),
    step_runs: Sequence[DependenceStepRun] = (),
    mastery: float | None = None,
) -> DependenceSignal:
    """按卡片汇总依赖度信号。

    规则：
    - 最近 3 条收据中至少 2 条 L4/L5，且至少 1 条 L5，记为 ``watch``；
    - 最近 5 条收据中至少 3 条 L4/L5，且至少 1 条 L5，且掌握度不低于
      0.4，记为 ``tighten``；
    - 追问命中率明显下降或同一步骤反复出错，只提高展示等级，不收紧提示。

    Args:
        card_id: 当前知识点卡。
        receipts: 历史收据；只使用同一卡片。
        dialog_events: 追问事件快照。
        step_runs: 步骤运行快照。
        mastery: 当前卡片掌握概率；None 视为未知，不收紧。

    Returns:
        ``DependenceSignal``；默认配置下需要至少 3 条收据才可能收紧。
    """
    ordered = _ordered_receipts(card_id, receipts)
    sample = len(ordered)
    recent = ordered[-WINDOW:]
    semi = sum(1 for item in recent if item.max_hint_level >= 4)
    l5 = sum(1 for item in recent if item.max_hint_level >= 5)
    reasons: list[str] = []

    watch = False
    tighten = False
    if len(ordered) >= MIN_RECEIPTS:
        last_three = ordered[-3:]
        if (
            sum(1 for item in last_three if item.max_hint_level >= 4)
            >= WATCH_SEMI
            and any(item.max_hint_level >= 5 for item in last_three)
        ):
            watch = True
            reasons.append("semi_independent_streak")
        if semi >= TIGHTEN_SEMI and l5 >= 1:
            reasons.append("semi_independent_density")
            if mastery is not None and mastery >= MASTERY_FLOOR:
                tighten = True
            else:
                watch = True

    if _dialog_anomaly(card_id, dialog_events):
        watch = True
        reasons.append("dialog_quality_drop")
    if _step_stuck(card_id, step_runs):
        watch = True
        reasons.append("step_stuck")

    if tighten:
        level = DependenceLevel.TIGHTEN
    elif watch:
        level = DependenceLevel.WATCH
    else:
        level = DependenceLevel.NONE

    return DependenceSignal(
        level=level,
        card_id=card_id,
        sample=sample,
        reasons=tuple(dict.fromkeys(reasons)),
        hint_ceiling=HINT_CEILING if tighten else None,
    )
