"""SM-2 简化调度：三档评分，ease 下限 1.3，interval 上限 30 天。"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

MIN_EASE = 1.3
DEFAULT_EASE = 2.5
DEFAULT_INTERVAL = 1
MAX_INTERVAL_DAYS = 30


class Quality(int, Enum):
    WRONG = 1        # 答错
    HINTED = 3       # 用了 L4 以上提示才做对
    INDEPENDENT = 5  # 独立做对


class Bucket(str, Enum):
    TODAY = "今天"
    TOMORROW = "明天"
    THREE_DAYS = "三天后"


@dataclass(frozen=True)
class Schedule:
    ease: float
    interval_days: int
    next_review_at: datetime


def update_schedule(ease: float, interval_days: int, quality: Quality, now: datetime) -> Schedule:
    """SM-2 简化版：答错重置为 1 天、ease 不变；做对按公式增长并封顶。"""
    if quality is Quality.WRONG:
        new_ease = ease
        new_interval = DEFAULT_INTERVAL
    else:
        q = quality.value
        # SM-2 标准 ease 增量公式；下限封底，避免难度过高时 ease 无限下降
        new_ease = max(MIN_EASE, ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
        if interval_days <= 1:
            # 首次做对：独立 3 天，带提示仍只给 1 天
            new_interval = 1 if quality is Quality.HINTED else 3
        else:
            # 后续按 ease 放大，并封顶 30 天，防止间隔失控
            new_interval = min(MAX_INTERVAL_DAYS, round(interval_days * new_ease))
    return Schedule(
        ease=new_ease,
        interval_days=new_interval,
        next_review_at=now + timedelta(days=new_interval),
    )


def bucket_for(interval_days: int) -> Bucket:
    """三档封顶：≤1 今天，≤3 明天，其余三天后。"""
    if interval_days <= 1:
        return Bucket.TODAY
    if interval_days <= 3:
        return Bucket.TOMORROW
    return Bucket.THREE_DAYS


def quality_from_outcome(judged: bool, max_hint_level: int) -> Quality:
    if not judged:
        return Quality.WRONG
    # L4 及以上视为未独立完成，只给短间隔
    if max_hint_level >= 4:
        return Quality.HINTED
    return Quality.INDEPENDENT
