"""本地时区日期与日界：每日挑战和复习调度统一使用本地零点。"""
from __future__ import annotations

from datetime import date, datetime, timedelta


def local_now() -> datetime:
    return datetime.now().astimezone()


def _local(value: datetime) -> datetime:
    """把带时区时间转换为本地时区；naive 时间按本地时间解释。"""
    return value.astimezone()


def local_day(value: datetime | None = None) -> date:
    return _local(value or local_now()).date()


def local_day_key(value: datetime | None = None) -> str:
    return local_day(value).isoformat()


def start_of_local_day(value: datetime) -> datetime:
    local = _local(value)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_local_day(value: datetime) -> datetime:
    local = _local(value)
    return local.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_local_day_after(value: datetime, days: int) -> datetime:
    return start_of_local_day(_local(value) + timedelta(days=days))
