"""本地时区日界：每日挑战与复习调度在本地零点切换。"""
import os
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    MistakeEntry,
    ReviewItem,
    Stage,
)
from mathcoach.memory.scheduler import build_plan, next_review
from mathcoach.timeutil import (
    end_of_local_day,
    local_day_key,
    start_of_local_day,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


@pytest.fixture
def shanghai(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """切换到上海时区并在结束后恢复。"""
    if not hasattr(time, "tzset"):
        pytest.skip("当前平台不支持 tzset")
    old = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "Asia/Shanghai")
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def _entry() -> MistakeEntry:
    """构造错题条目样例。"""
    return MistakeEntry(
        id="m1",
        exercise_id="e1",
        card_id="c1",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错答",
        correct_answer="正确",
        error_type=ErrorType.CONCEPT,
        max_hint_level=1,
        created_at=datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc),
    )


def test_local_day_key_switches_at_local_midnight(shanghai):
    """日键在本地零点切换。"""
    before = datetime(2026, 11, 20, 15, 59, tzinfo=timezone.utc)
    after = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)

    assert local_day_key(before) == "2026-11-20"
    assert local_day_key(after) == "2026-11-21"


def test_local_day_boundaries_are_midnight(shanghai):
    """本地日边界为当日零点与二十三点五十九分。"""
    value = datetime(2026, 11, 20, 17, 0, tzinfo=timezone.utc)
    start = start_of_local_day(value)
    end = end_of_local_day(value)

    assert (start.date(), start.hour, start.minute, start.second) == (
        date(2026, 11, 21),
        0,
        0,
        0,
    )
    assert (end.date(), end.hour, end.minute) == (date(2026, 11, 21), 23, 59)
    assert start.utcoffset() == timedelta(hours=8)


def test_review_due_at_local_midnight(shanghai):
    """复习到期时间落在本地零点。"""
    now = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    _, _, _, due_at = next_review(_entry(), True, now)

    assert due_at is not None
    local_due = due_at.astimezone(SHANGHAI)
    assert (local_due.date(), local_due.hour, local_due.minute) == (
        date(2026, 11, 21),
        0,
        0,
    )


def test_review_buckets_roll_over_at_local_midnight(shanghai):
    """复习桶在本地零点滚动。"""
    now_local = datetime(2026, 11, 20, 18, 0, tzinfo=SHANGHAI)
    now_utc = now_local.astimezone(timezone.utc)
    entry = _entry()
    today_item = ReviewItem(entry, now_local.replace(hour=23, minute=0))
    tomorrow_item = ReviewItem(
        entry, now_local.replace(hour=0, minute=0) + timedelta(days=1)
    )

    plan = build_plan([today_item, tomorrow_item], now_utc)
    assert today_item in plan.today
    assert tomorrow_item in plan.tomorrow
