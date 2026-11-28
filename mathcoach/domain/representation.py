"""表示降级：按行为信号选择讲解形态，不参与判分与掌握度更新。

只输出教学呈现建议；BKT 掌握概率、FSRS 调度与 verify 数学判定都不读取
本模块。触发规则采用“多类信号”门槛，避免单次异常就改变讲解形态。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

CONSECUTIVE_WRONG_THRESHOLD = 2
HINT_REQUEST_THRESHOLD = 1
ELAPSED_RATIO_THRESHOLD = 1.5
MISSING_STEPS_THRESHOLD = 2
MIN_SIGNAL_KINDS = 2


class Representation(str, Enum):
    """讲解表示形态，从抽象到具体。"""

    FORMULA = "formula"
    WORKED_EXAMPLE = "worked_example"
    CONCRETE_VISUAL = "concrete_visual"


@dataclass(frozen=True)
class LoadSignals:
    """一次表示决策可用的行为信号；缺失字段按 0/False 处理。"""

    consecutive_wrong: int = 0
    dialog_misses: int = 0
    hint_requests: int = 0
    elapsed_ratio: float = 0.0
    missing_steps: int = 0
    abandoned: bool = False


@dataclass(frozen=True)
class RepresentationDecision:
    """表示决策结果；``reasons`` 记录触发信号，便于效果回看。"""

    base: Representation
    target: Representation
    reasons: tuple[str, ...] = ()

    @property
    def downgraded(self) -> bool:
        """是否发生了降级。"""
        return self.target is not self.base


def _signal_reasons(signals: LoadSignals) -> list[str]:
    """收集命中的信号类型，每种类型最多记一条。"""
    reasons: list[str] = []
    if signals.consecutive_wrong >= CONSECUTIVE_WRONG_THRESHOLD:
        reasons.append(f"连续错误={signals.consecutive_wrong}")
    if signals.dialog_misses >= 1:
        reasons.append(f"追问未命中={signals.dialog_misses}")
    if signals.hint_requests >= HINT_REQUEST_THRESHOLD:
        reasons.append(f"提示请求={signals.hint_requests}")
    if signals.elapsed_ratio >= ELAPSED_RATIO_THRESHOLD:
        reasons.append(f"耗时比={signals.elapsed_ratio:.2f}")
    if signals.missing_steps >= 1:
        reasons.append(f"缺失步骤={signals.missing_steps}")
    return reasons


def choose_representation(
    base: Representation = Representation.FORMULA,
    signals: LoadSignals | None = None,
    *,
    allow_visual: bool = False,
) -> RepresentationDecision:
    """按信号选择讲解形态；单信号不降级。

    规则：

    - 硬信号：中途放弃，或连续缺失 ≥2 步，立即降一级；
    - 软信号：连续错误 ≥2、追问未命中、请求过提示、耗时 ≥1.5 倍参考、
      出现过缺失步骤；至少命中 2 类才降一级；
    - 每题只降一级：FORMULA → WORKED_EXAMPLE；只有当前已经是
      WORKED_EXAMPLE 且 ``allow_visual`` 为真时才继续到 CONCRETE_VISUAL。

    Args:
        base: 当前讲解形态。
        signals: 行为信号；None 表示没有可用信号。
        allow_visual: 是否允许降到配图/图形形态。

    Returns:
        ``RepresentationDecision``；未降级时 ``target`` 与 ``base`` 相同。
    """
    active = signals or LoadSignals()
    reasons = _signal_reasons(active)
    hard = active.abandoned or active.missing_steps >= MISSING_STEPS_THRESHOLD
    if hard:
        reasons.append("放弃或连续缺失步骤")
    if not hard and len(reasons) < MIN_SIGNAL_KINDS:
        return RepresentationDecision(base, base, ())
    if base is Representation.FORMULA:
        target = Representation.WORKED_EXAMPLE
    elif base is Representation.WORKED_EXAMPLE and allow_visual:
        target = Representation.CONCRETE_VISUAL
    else:
        target = base
    if target is base:
        return RepresentationDecision(base, base, ())
    return RepresentationDecision(base, target, tuple(reasons))
