"""周报与错因趋势：时间窗口、每日收据与环比文字。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    Stage,
)
from mathcoach.memory.report import build_error_trend, build_weekly_report
from mathcoach.memory.repository import InMemoryRepository

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


def _receipt(identifier: str, days_ago: int, independence: Independence) -> Receipt:
    return Receipt(
        id=identifier,
        card_id="card-1",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=10,
        max_hint_level=2,
        goal="练",
        independence=independence,
        created_at=NOW - timedelta(days=days_ago),
    )


def _mistake(
    identifier: str, days_ago: int, error: ErrorType, exercise_id: str
) -> MistakeEntry:
    return MistakeEntry(
        id=identifier,
        exercise_id=exercise_id,
        card_id="card-1",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错",
        correct_answer="对",
        error_type=error,
        max_hint_level=1,
        created_at=NOW - timedelta(days=days_ago),
    )


def _repository() -> InMemoryRepository:
    repository = InMemoryRepository()
    repository.save_receipt(_receipt("r1", 0, Independence.INDEPENDENT), "e1")
    repository.save_receipt(_receipt("r2", 3, Independence.SEMI_INDEPENDENT), "e2")
    repository.save_receipt(_receipt("r3", 10, Independence.INDEPENDENT), "e3")
    repository.save_mistake(_mistake("m1", 0, ErrorType.CONCEPT, "e1"))
    repository.save_mistake(_mistake("m2", 1, ErrorType.CONCEPT, "e2"))
    repository.save_mistake(_mistake("m3", 8, ErrorType.CALCULATION, "e3"))
    repository.save_mistake(_mistake("m4", 9, ErrorType.CALCULATION, "e4"))
    return repository


def test_weekly_report_filters_last_seven_days():
    report = build_weekly_report(_repository(), NOW)

    assert report.start.isoformat() == "2026-11-14"
    assert report.end.isoformat() == "2026-11-20"
    assert report.receipts == 2
    assert report.independent == 1
    assert report.mistakes == 2
    assert report.average_hint_level == 2.0
    assert len(report.daily_receipts) == 7
    assert dict(report.daily_receipts)["2026-11-20"] == 1
    assert dict(report.top_errors) == {ErrorType.CONCEPT.value: 2}


def test_error_trend_compares_with_last_week():
    trend = build_error_trend(_repository().list_mistakes(limit=None), NOW)

    assert dict(trend.this_week) == {ErrorType.CONCEPT.value: 2}
    assert dict(trend.last_week) == {ErrorType.CALCULATION.value: 2}
    assert "概念不清 2 次（较上周 +2）" in trend.summary


def test_error_trend_empty_week_text():
    trend = build_error_trend([], NOW)
    assert trend.this_week == ()
    assert "没有新增错题" in trend.summary


def test_error_trend_ignores_future_mistakes():
    future = _mistake("m5", -3, ErrorType.CONCEPT, "e5")

    trend = build_error_trend([future], NOW)

    assert trend.this_week == ()
    assert trend.last_week == ()
    assert "没有新增错题" in trend.summary


def test_weekly_report_compares_mastery_with_pre_week_baseline():
    repository = InMemoryRepository()
    repository.set_mastery("card-1", 0.40, NOW - timedelta(days=8))
    repository.set_mastery("card-1", 0.55, NOW - timedelta(days=3))
    repository.set_mastery("card-1", 0.70, NOW)

    report = build_weekly_report(repository, NOW)

    assert len(report.mastery_changes) == 1
    change = report.mastery_changes[0]
    assert change.card_id == "card-1"
    assert round(change.before, 2) == 0.40
    assert round(change.after, 2) == 0.70
    assert round(change.delta, 2) == 0.30


def test_weekly_report_skips_mastery_without_change_or_week_activity():
    repository = InMemoryRepository()
    repository.set_mastery("card-1", 0.50, NOW - timedelta(days=1))
    repository.set_mastery("card-2", 0.30, NOW - timedelta(days=10))

    report = build_weekly_report(repository, NOW)

    assert report.mastery_changes == ()


def test_mastery_changes_sorted_by_absolute_change():
    repository = InMemoryRepository()
    repository.set_mastery("a", 0.40, NOW - timedelta(days=8))
    repository.set_mastery("a", 0.50, NOW)
    repository.set_mastery("b", 0.40, NOW - timedelta(days=8))
    repository.set_mastery("b", 0.90, NOW)

    report = build_weekly_report(repository, NOW)

    assert [change.card_id for change in report.mastery_changes] == [
        "b",
        "a",
    ]
