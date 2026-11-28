"""速度观测权重：耗时只影响 BKT 观测权重，不修改 BKT 公式。"""
from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from ..domain.models import Receipt
from ..domain.spaced_repetition import Quality, quality_from_outcome

DEFAULT_REFERENCE_S = 60.0
DEFAULT_WEAK_RATIO = 1.5
DEFAULT_FLOOR_WEIGHT = 0.5
DEFAULT_MAX_DURATION_S = 3600
DEFAULT_MIN_SAMPLES = 3

ENV_REFERENCE_S = "MATHCOACH_SPEED_REFERENCE_S"
ENV_WEAK_RATIO = "MATHCOACH_SPEED_WEAK_RATIO"
ENV_FLOOR_WEIGHT = "MATHCOACH_SPEED_FLOOR_WEIGHT"
ENV_MAX_DURATION_S = "MATHCOACH_SPEED_MAX_DURATION_S"
ENV_MIN_SAMPLES = "MATHCOACH_SPEED_MIN_SAMPLES"


@dataclass(frozen=True)
class SpeedPolicy:
    """速度权重策略；阈值与权重都可显式注入，便于测试与后续配置。"""

    reference_s: float = DEFAULT_REFERENCE_S
    weak_ratio: float = DEFAULT_WEAK_RATIO
    floor_weight: float = DEFAULT_FLOOR_WEIGHT
    max_duration_s: int = DEFAULT_MAX_DURATION_S
    min_samples: int = DEFAULT_MIN_SAMPLES

    def __post_init__(self) -> None:
        """校验策略参数范围。"""
        if self.reference_s <= 0:
            raise ValueError("reference_s 必须大于 0")
        if self.weak_ratio < 1.0:
            raise ValueError("weak_ratio 必须不小于 1")
        if not 0.0 <= self.floor_weight <= 1.0:
            raise ValueError("floor_weight 必须在 [0, 1] 内")
        if self.max_duration_s <= 0:
            raise ValueError("max_duration_s 必须大于 0")
        if self.min_samples < 1:
            raise ValueError("min_samples 必须不小于 1")


DEFAULT_POLICY = SpeedPolicy()


def _env_float(name: str, fallback: float) -> float:
    """读取浮点环境变量；缺失或非法时回退。"""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return fallback
    try:
        return float(raw)
    except ValueError:
        return fallback


def _env_int(name: str, fallback: int) -> int:
    """读取整数环境变量；缺失或非法时回退。"""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def load_speed_policy() -> SpeedPolicy:
    """从环境变量读取策略；非法值回退内置默认。"""
    try:
        return SpeedPolicy(
            reference_s=_env_float(
                ENV_REFERENCE_S, DEFAULT_REFERENCE_S
            ),
            weak_ratio=_env_float(ENV_WEAK_RATIO, DEFAULT_WEAK_RATIO),
            floor_weight=_env_float(
                ENV_FLOOR_WEIGHT, DEFAULT_FLOOR_WEIGHT
            ),
            max_duration_s=_env_int(
                ENV_MAX_DURATION_S, DEFAULT_MAX_DURATION_S
            ),
            min_samples=_env_int(ENV_MIN_SAMPLES, DEFAULT_MIN_SAMPLES),
        )
    except ValueError:
        return DEFAULT_POLICY


def normalize_duration(
    duration_s: float | int | None,
    policy: SpeedPolicy | None = None,
) -> float:
    """截断异常耗时；非正数视为未知时长，返回 0。"""
    active = policy or load_speed_policy()
    if duration_s is None:
        return 0.0
    value = float(duration_s)
    if value <= 0:
        return 0.0
    return min(value, float(active.max_duration_s))


def observation_weight(
    duration_s: float | int | None,
    reference_s: float,
    policy: SpeedPolicy | None = None,
) -> float:
    """按耗时返回 BKT 观测权重。

    ``duration <= reference * weak_ratio`` 返回 1.0；之后线性下降，
    到 ``reference * weak_ratio * 2`` 时达到 ``floor_weight`` 并保持不变。
    未知或非正耗时返回 1.0，避免把缺失数据当成慢速。

    Args:
        duration_s: 本题耗时；None 或非正数表示未知。
        reference_s: 参考耗时；非正时使用策略默认值。
        policy: 速度策略；None 时读取环境变量。

    Returns:
        [floor_weight, 1.0] 内的观测权重。
    """
    active = policy or load_speed_policy()
    reference = (
        reference_s if reference_s > 0 else active.reference_s
    )
    duration = normalize_duration(duration_s, active)
    if duration <= 0:
        return 1.0
    weak_start = reference * active.weak_ratio
    if duration <= weak_start:
        return 1.0
    floor_start = weak_start * 2.0
    if duration >= floor_start:
        return active.floor_weight
    progress = (duration - weak_start) / (floor_start - weak_start)
    return 1.0 - progress * (1.0 - active.floor_weight)


def is_weak_correct(
    duration_s: float | int | None,
    reference_s: float,
    policy: SpeedPolicy | None = None,
) -> bool:
    """是否正确但超过弱观测阈值。"""
    return observation_weight(duration_s, reference_s, policy) < 1.0


def reference_seconds_from_history(
    receipts: Sequence[Receipt],
    card_id: str | None = None,
    *,
    policy: SpeedPolicy | None = None,
    default: float | None = None,
) -> float:
    """用历史收据的中位数作为参考耗时。

    只使用正数且不超过 ``max_duration_s`` 的记录；样本少于
    ``min_samples`` 时回退默认值。

    Args:
        receipts: 历史收据。
        card_id: 只统计该卡；None 表示全部。
        policy: 速度策略。
        default: 样本不足时的回退值；None 使用策略默认。

    Returns:
        参考耗时秒数。
    """
    active = policy or load_speed_policy()
    fallback = default if default is not None else active.reference_s
    durations = [
        float(receipt.duration_s)
        for receipt in receipts
        if (card_id is None or receipt.card_id == card_id)
        and 0 < receipt.duration_s <= active.max_duration_s
    ]
    if len(durations) < active.min_samples:
        return fallback
    value = float(median(durations))
    return value if value > 0 else fallback


def quality_for_correct(
    duration_s: float | int | None,
    reference_s: float,
    max_hint_level: int = 0,
    policy: SpeedPolicy | None = None,
) -> Quality:
    """把正确作答映射成 FSRS/BKT 评分；弱正确按 HINTED 处理。

    只复用现有 ``Quality.HINTED`` 语义，不修改 FSRS 调度算法。
    """
    if is_weak_correct(duration_s, reference_s, policy):
        return Quality.HINTED
    return quality_from_outcome(True, max_hint_level)
