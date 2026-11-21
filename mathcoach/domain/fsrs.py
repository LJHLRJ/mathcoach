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
    AGAIN = 1  # 未通过/遗忘
    HARD = 2   # 勉强回忆
    GOOD = 3   # 正常回忆
    EASY = 4   # 轻松回忆


@dataclass(frozen=True)
class MemoryState:
    stability: float  # 记忆稳定性，单位：天
    difficulty: float  # 难度 1..10
    reps: int = 0
    lapses: int = 0


@dataclass(frozen=True)
class FsrsParams:
    weights: tuple[float, ...] = DEFAULT_WEIGHTS
    desired_retention: float = DEFAULT_DESIRED_RETENTION
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS

    def __post_init__(self) -> None:
        if len(self.weights) != 17:
            raise ValueError("FSRS 权重必须是 17 个")
        if not 0 < self.desired_retention <= 1:
            raise ValueError("desired_retention 必须在 (0, 1] 内")
        if self.max_interval_days < 1:
            raise ValueError("max_interval_days 必须 >= 1")


DEFAULT_PARAMS = FsrsParams()


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _initial_difficulty(rating: Rating, params: FsrsParams) -> float:
    w = params.weights
    # FSRS 初始难度：评分越高，初始难度越低
    raw = w[4] - exp(w[5] * (rating.value - 1)) + 1
    return _clamp(raw, MIN_DIFFICULTY, MAX_DIFFICULTY)


def _next_difficulty(current: float, rating: Rating, params: FsrsParams) -> float:
    w = params.weights
    # 评分低于 Good 时难度上升，高于 Good 时下降
    updated = current - w[6] * (rating.value - 3)
    # 向初始难度均值回归，避免难度长期漂移
    easy_initial = _initial_difficulty(Rating.EASY, params)
    updated = w[7] * easy_initial + (1 - w[7]) * updated
    return _clamp(updated, MIN_DIFFICULTY, MAX_DIFFICULTY)


def retrievability(stability: float, elapsed_days: float) -> float:
    """给定稳定性与已经过天数，返回当前可提取概率。"""
    if stability <= 0:
        return 0.0
    elapsed = max(0.0, float(elapsed_days))
    return (1 + FACTOR * elapsed / stability) ** DECAY


def interval_from_retrievability(
    stability: float,
    desired_retention: float = DEFAULT_DESIRED_RETENTION,
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS,
) -> int:
    """反解遗忘曲线：达到目标保持率所需的间隔天数。"""
    if stability <= 0:
        return 1
    raw = stability / FACTOR * (desired_retention ** (1 / DECAY) - 1)
    # 至少 1 天，并受最大间隔限制，防止异常状态产生无限间隔
    return int(_clamp(round(raw), 1, max_interval_days))


def initial_state(rating: Rating, params: FsrsParams = DEFAULT_PARAMS) -> MemoryState:
    """首次评分后的初始记忆状态。"""
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
    """根据一次评分更新记忆状态，返回 (新状态, 下次间隔天数)。"""
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
    """从 YAML 映射构造参数；缺失字段回落到默认值。"""
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
