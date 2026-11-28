"""教学后作答的 KC 掌握回流：只计算确定性更新，不写数据库。

状态持久化仍由现有仓储路径完成；这里不直接修改 BKT 表。
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from ..domain.bkt import (
    BKTParams,
    bkt_params,
    initial_mastery,
    update_mastery,
)
from ..domain.spaced_repetition import Quality

PRETEST_WEIGHT = 0.0
PRETEST_COUNTED_WEIGHT = 0.25
IMMEDIATE_WEIGHT = 1.0
DELAYED_WEIGHT = 1.0
MAX_IMMEDIATE_DROP = 0.15


@dataclass(frozen=True)
class TeachingAttempt:
    """一次教学相关作答；``source`` 决定回流权重。"""

    kc_ids: tuple[str, ...]
    correct: bool
    quality: Quality | None = None
    source: Literal["pretest", "immediate", "delayed"] = "immediate"


def _weight(source: str, count_pretest: bool) -> float:
    """返回不同来源的 BKT 更新权重。"""
    if source == "pretest":
        return PRETEST_COUNTED_WEIGHT if count_pretest else PRETEST_WEIGHT
    if source == "delayed":
        return DELAYED_WEIGHT
    return IMMEDIATE_WEIGHT


def apply_attempt(
    priors: Mapping[str, float],
    attempt: TeachingAttempt,
    *,
    params: BKTParams | None = None,
    count_pretest: bool = False,
) -> dict[str, float]:
    """按来源权重计算 KC 掌握概率更新。

    教学前测默认不更新正式 BKT；教学后即时答错限制单次跌幅；
    延迟复习按完整 BKT 更新。返回值为新概率，不落库。

    Args:
        priors: KC ID -> 当前掌握概率。
        attempt: 一次作答。
        params: BKT 四参数；None 时读取 content/bkt_params.yaml。
        count_pretest: 是否允许前测计入正式 BKT。

    Returns:
        KC ID -> 更新后的掌握概率。
    """
    active = params or bkt_params()
    weight = _weight(attempt.source, count_pretest)
    updates: dict[str, float] = {}
    for kc_id in attempt.kc_ids:
        prior = priors.get(kc_id)
        if prior is None:
            prior = initial_mastery(active)
        updated = update_mastery(
            prior,
            attempt.correct,
            active,
            quality=attempt.quality,
        )
        if attempt.source == "immediate" and not attempt.correct:
            updated = max(updated, prior - MAX_IMMEDIATE_DROP)
        value = prior + weight * (updated - prior)
        updates[kc_id] = max(0.0, min(1.0, value))
    return updates
