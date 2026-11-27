"""BKT 纯函数：四参数掌握概率更新，不读数据库、不读时钟。"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

import yaml


def _clamp(value: float, lower: float, upper: float) -> float:
    """把 value 截到 [lower, upper]。"""
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class BKTParams:
    """BKT 四参数；全部取值必须在 [0, 1]。"""

    p_init: float = 0.3      # 初始掌握概率
    p_transit: float = 0.1   # 每次观察后的学习转移概率
    p_guess: float = 0.2     # 未掌握时猜对的概率
    p_slip: float = 0.1      # 已掌握时失误的概率

    def __post_init__(self) -> None:
        """校验四个参数都在 [0, 1]；越界抛 ValueError。"""
        for name in ("p_init", "p_transit", "p_guess", "p_slip"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} 必须在 [0, 1] 内")


DEFAULT_BKT_PARAMS = BKTParams()


def initial_mastery(params: BKTParams = DEFAULT_BKT_PARAMS) -> float:
    """新知识点的初始掌握概率，等于 ``p_init``。"""
    return params.p_init


def update_mastery(
    prior: float, correct: bool, params: BKTParams = DEFAULT_BKT_PARAMS
) -> float:
    """一次观察后的掌握概率：先算贝叶斯后验，再加学习转移。

    答对时用“已掌握且未失误 / 未掌握但猜对”，答错时用“已掌握但失误 /
    未掌握且未猜对”；最后把未掌握部分按 ``p_transit`` 转成掌握。

    Args:
        prior: 观察前的掌握概率，越界会被截到 [0, 1]。
        correct: 本次是否答对。
        params: BKT 四参数。

    Returns:
        更新后的掌握概率，范围 [0, 1]。
    """
    prior = _clamp(prior, 0.0, 1.0)
    if correct:
        # 已掌握且未失误 vs 未掌握但猜对
        numerator = (1 - params.p_slip) * prior
        denominator = numerator + params.p_guess * (1 - prior)
    else:
        # 已掌握但失误 vs 未掌握且未猜对
        numerator = params.p_slip * prior
        denominator = numerator + (1 - params.p_guess) * (1 - prior)
    posterior = numerator / denominator if denominator > 0 else prior
    # 学习转移：未掌握部分按 p_transit 转化为掌握
    next_mastery = posterior + (1 - posterior) * params.p_transit
    return _clamp(next_mastery, 0.0, 1.0)


def params_from_mapping(data: Mapping[str, object]) -> BKTParams:
    """从 YAML 映射构造参数；缺失字段用内置默认值。

    Args:
        data: 解析后的 ``bkt_params.yaml`` 内容。

    Returns:
        ``BKTParams``；取值越界时由构造函数抛 ValueError。
    """
    return BKTParams(
        p_init=float(data.get("p_init", DEFAULT_BKT_PARAMS.p_init)),
        p_transit=float(data.get("p_transit", DEFAULT_BKT_PARAMS.p_transit)),
        p_guess=float(data.get("p_guess", DEFAULT_BKT_PARAMS.p_guess)),
        p_slip=float(data.get("p_slip", DEFAULT_BKT_PARAMS.p_slip)),
    )


@lru_cache(maxsize=1)
def bkt_params() -> BKTParams:
    """读取 content/bkt_params.yaml；缺失时回落到内置默认参数。"""
    path = Path(__file__).resolve().parents[2] / "content" / "bkt_params.yaml"
    if not path.exists():
        return DEFAULT_BKT_PARAMS
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return params_from_mapping(data)
