"""SM-2 简化调度：三档评分、ease 下限、interval 上限、bucket 映射。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.spaced_repetition import (
    Bucket,
    MAX_INTERVAL_DAYS,
    MIN_EASE,
    Quality,
    bucket_for,
    quality_from_independence,
    quality_from_outcome,
    update_schedule,
)

NOW = datetime(2026, 11, 21, tzinfo=timezone.utc)


def test_wrong_resets_interval_and_keeps_ease():
    sched = update_schedule(ease=2.5, interval_days=10, quality=Quality.WRONG, now=NOW)
    assert sched.interval_days == 1
    assert sched.ease == 2.5
    assert sched.next_review_at == NOW + timedelta(days=1)


def test_independent_grows_interval_and_ease():
    sched = update_schedule(ease=2.5, interval_days=1, quality=Quality.INDEPENDENT, now=NOW)
    assert sched.interval_days == 3
    assert sched.ease > 2.5


def test_hinted_keeps_interval_short():
    sched = update_schedule(ease=2.5, interval_days=1, quality=Quality.HINTED, now=NOW)
    assert sched.interval_days == 1


def test_ease_never_below_min():
    sched = update_schedule(ease=1.3, interval_days=5, quality=Quality.HINTED, now=NOW)
    assert sched.ease >= MIN_EASE


def test_interval_capped_at_max():
    sched = update_schedule(ease=2.5, interval_days=28, quality=Quality.INDEPENDENT, now=NOW)
    assert sched.interval_days == MAX_INTERVAL_DAYS


def test_bucket_mapping():
    assert bucket_for(1) is Bucket.TODAY
    assert bucket_for(3) is Bucket.TOMORROW
    assert bucket_for(10) is Bucket.THREE_DAYS


def test_quality_from_outcome():
    assert quality_from_outcome(judged=False, max_hint_level=1) is Quality.WRONG
    assert quality_from_outcome(judged=True, max_hint_level=1) is Quality.INDEPENDENT
    assert quality_from_outcome(judged=True, max_hint_level=4) is Quality.HINTED


def test_quality_from_independence():
    assert quality_from_independence(True) is Quality.INDEPENDENT
    assert quality_from_independence(False) is Quality.WRONG
