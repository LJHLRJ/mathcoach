"""FSRS v4 纯函数：不读数据库、不读时钟，状态与评分全部显式传入。

权重采用 FSRS v4 默认值；首期不做参数拟合，目标保持率固定 0.9。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp
from typing import Mapping

# FSRS 遗忘曲线常量：R(t, S) = (1 + FACTOR * t / S) ** DECAY
FACTOR = 19 / 81
DECAY = -0.5
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0
MIN_STABILITY = 0.1
DEFAULT_DESIRED_RETENTION = 0.9
DEFAULT_MAX_INTERVAL_DAYS = 365

# FSRS v4 默认的 17 个权重（w0..w16）
DEFAULT_WEIGHTS: tuple[float, ...] = (
    0.4072,
    1.1829,
    3.1262,
    15.4722,
    7.2102,
    0.5316,
    1.0651,
    0.0234,
    1.6160,
    0.1544,
    1.0824,
    1.9813,
    0.0953,
    0.2975,
    2.2042,
    0.2407,
    2.9466,
)


class Rating(int, Enum):
    """FSRS 的四档评分，取值 1–4 与权重下标一一对应。"""

    AGAIN = 1  # 未通过/遗忘
    HARD = 2   # 勉强回忆
    GOOD = 3   # 正常回忆
    EASY = 4   # 轻松回忆


@dataclass(frozen=True)
class MemoryState:
    """单张卡片的 FSRS 记忆状态；``stability`` 单位为天，``difficulty`` 为 1–10。"""

    stability: float  # 记忆稳定性，单位：天
    difficulty: float  # 难度 1..10
    reps: int = 0
    lapses: int = 0


@dataclass(frozen=True)
class FsrsParams:
    """FSRS 权重与目标保持率；构造时校验范围。

    ``weights`` 必须是 17 个；``desired_retention`` 在 (0, 1]；``max_interval_days`` ≥ 1。
    """

    weights: tuple[float, ...] = DEFAULT_WEIGHTS
    desired_retention: float = DEFAULT_DESIRED_RETENTION
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS

    def __post_init__(self) -> None:
        """校验权重数量与参数范围，不合法时抛 ValueError。"""
        if len(self.weights) != 17:
            raise ValueError("FSRS 权重必须是 17 个")
        if not 0 < self.desired_retention <= 1:
            raise ValueError("desired_retention 必须在 (0, 1] 内")
        if self.max_interval_days < 1:
            raise ValueError("max_interval_days 必须 >= 1")


DEFAULT_PARAMS = FsrsParams()


def _clamp(value: float, lower: float, upper: float) -> float:
    """把数值限制在闭区间 [lower, upper]。"""
    return max(lower, min(upper, value))


def _initial_difficulty(rating: Rating, params: FsrsParams) -> float:
    """首次评分后的难度：评分越高，初始难度越低。"""
    w = params.weights
    raw = w[4] - exp(w[5] * (rating.value - 1)) + 1
    return _clamp(raw, MIN_DIFFICULTY, MAX_DIFFICULTY)


def _next_difficulty(current: float, rating: Rating, params: FsrsParams) -> float:
    """按评分更新难度，并向初始难度均值回归，结果限制在 1–10。"""
    w = params.weights
    # 评分低于 Good 时难度上升，高于 Good 时下降
    updated = current - w[6] * (rating.value - 3)
    # 向初始难度均值回归，避免难度长期漂移
    easy_initial = _initial_difficulty(Rating.EASY, params)
    updated = w[7] * easy_initial + (1 - w[7]) * updated
    return _clamp(updated, MIN_DIFFICULTY, MAX_DIFFICULTY)


def retrievability(stability: float, elapsed_days: float) -> float:
    """按遗忘曲线计算当前可提取概率。

    ``R(t, S) = (1 + FACTOR * t / S) ** DECAY``，t 为距上次复习的天数。

    Args:
        stability: 记忆稳定性（天）；≤ 0 时直接返回 0。
        elapsed_days: 已经过天数，负数按 0 处理。

    Returns:
        0–1 之间的可提取概率。
    """
    if stability <= 0:
        return 0.0
    elapsed = max(0.0, float(elapsed_days))
    return (1 + FACTOR * elapsed / stability) ** DECAY


def interval_from_retrievability(
    stability: float,
    desired_retention: float = DEFAULT_DESIRED_RETENTION,
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS,
) -> int:
    """反解遗忘曲线，求达到目标保持率所需的间隔天数。

    Args:
        stability: 记忆稳定性（天）；≤ 0 时返回 1。
        desired_retention: 目标可提取概率，取值 (0, 1]。
        max_interval_days: 间隔上限，避免异常状态产生无限间隔。

    Returns:
        至少 1、至多 ``max_interval_days`` 的整数天数。
    """
    if stability <= 0:
        return 1
    raw = stability / FACTOR * (desired_retention ** (1 / DECAY) - 1)
    # 至少 1 天，并受最大间隔限制，防止异常状态产生无限间隔
    return int(_clamp(round(raw), 1, max_interval_days))


def initial_state(rating: Rating, params: FsrsParams = DEFAULT_PARAMS) -> MemoryState:
    """首次评分后的初始记忆状态。

    ``AGAIN`` 记为 1 次遗忘；其余评分 ``lapses`` 为 0。

    Args:
        rating: 首次评分。
        params: FSRS 参数。

    Returns:
        稳定性取对应权重（下限 ``MIN_STABILITY``），``reps`` 为 1。
    """
    stability = max(MIN_STABILITY, params.weights[rating.value - 1])
    return MemoryState(
        stability=stability,
        difficulty=_initial_difficulty(rating, params),
        reps=1,
        lapses=1 if rating is Rating.AGAIN else 0,
    )


def review(
    state: MemoryState,
    rating: Rating,
    elapsed_days: float,
    params: FsrsParams = DEFAULT_PARAMS,
) -> tuple[MemoryState, int]:
    """按一次评分更新记忆状态，并给出下次间隔。

    ``AGAIN`` 走遗忘分支：稳定性重估后不允许高于原值，``lapses`` 加 1；
    其余评分走成功分支：难度越低、可提取率越低，稳定性增益越大，
    ``HARD`` 乘惩罚系数、``EASY`` 乘奖励系数。

    Args:
        state: 当前记忆状态。
        rating: 本次评分。
        elapsed_days: 距上次复习的天数，传给遗忘曲线计算可提取率。
        params: FSRS 参数。

    Returns:
        ``(新状态, 间隔天数)``；间隔由新稳定性反解目标保持率得到。
    """
    w = params.weights
    current_retrievability = retrievability(state.stability, elapsed_days)
    new_difficulty = _next_difficulty(state.difficulty, rating, params)

    if rating is Rating.AGAIN:
        # 遗忘后的稳定性重估；不允许比遗忘前更高
        recalled = (
            w[11]
            * (state.difficulty ** -w[12])
            * ((state.stability + 1) ** w[13] - 1)
            * exp((1 - current_retrievability) * w[14])
        )
        new_stability = min(state.stability, recalled)
        lapses = state.lapses + 1
    else:
        # 成功回忆：难度越低、可提取率越低，稳定性增益越大
        hard_penalty = w[15] if rating is Rating.HARD else 1.0
        easy_bonus = w[16] if rating is Rating.EASY else 1.0
        new_stability = state.stability * (
            1
            + exp(w[8])
            * (11 - new_difficulty)
            * (state.stability ** -w[9])
            * (exp((1 - current_retrievability) * w[10]) - 1)
            * hard_penalty
            * easy_bonus
        )
        lapses = state.lapses

    new_stability = max(MIN_STABILITY, new_stability)
    new_state = MemoryState(
        stability=new_stability,
        difficulty=new_difficulty,
        reps=state.reps + 1,
        lapses=lapses,
    )
    interval = interval_from_retrievability(
        new_stability,
        params.desired_retention,
        params.max_interval_days,
    )
    return new_state, interval


def params_from_mapping(data: Mapping[str, object]) -> FsrsParams:
    """从 YAML 映射构造参数；缺失字段回落到默认值。

    Args:
        data: 解析后的 ``fsrs_params.yaml`` 内容。

    Returns:
        ``FsrsParams``；权重个数不是 17 时由构造函数抛 ValueError。
    """
    raw_weights = data.get("weights")
    if raw_weights is None:
        weights = DEFAULT_WEIGHTS
    else:
        weights = tuple(float(value) for value in raw_weights)  # type: ignore[arg-type]
    return FsrsParams(
        weights=weights,
        desired_retention=float(data.get("desired_retention", DEFAULT_DESIRED_RETENTION)),
        max_interval_days=int(data.get("max_interval_days", DEFAULT_MAX_INTERVAL_DAYS)),
    )
