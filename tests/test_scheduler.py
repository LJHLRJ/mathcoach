"""复习调度：三档清单、上限、掌握门槛。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    MistakeEntry,
    ReviewItem,
    ReviewState,
    Stage,
)
from mathcoach.memory.scheduler import build_plan, next_review

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


def _entry(identifier: str = "m1", **fields) -> MistakeEntry:
    return MistakeEntry(
        id=identifier,
        exercise_id=f"e-{identifier}",
        card_id="card-1",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错答",
        correct_answer="正确",
        error_type=ErrorType.CONCEPT,
        max_hint_level=1,
        created_at=NOW,
        **fields,
    )


def test_first_independent_correct_schedules_tomorrow():
    state, count, streak, due_at = next_review(_entry(), True, NOW)
    assert state is ReviewState.REVIEWING
    assert count == 1
    assert streak == 1
    assert due_at is not None
    assert due_at.date() == (NOW + timedelta(days=1)).date()


def test_two_independent_corrects_master_the_entry():
    entry = _entry(review_state=ReviewState.REVIEWING, review_count=1, consecutive_correct=1)
    state, count, streak, due_at = next_review(entry, True, NOW)
    assert state is ReviewState.MASTERED
    assert count == 2
    assert streak == 2
    assert due_at is None


def test_semi_independent_review_resets_streak_and_delays_three_days():
    entry = _entry(consecutive_correct=1)
    state, count, streak, due_at = next_review(entry, False, NOW)
    assert state is ReviewState.REVIEWING
    assert count == 1
    assert streak == 0
    assert due_at is not None
    assert due_at.date() == (NOW + timedelta(days=3)).date()


def test_plan_caps_each_bucket_at_three():
    items = []
    for index in range(5):
        items.append(ReviewItem(_entry(f"today-{index}"), NOW))
    for index in range(5):
        items.append(
            ReviewItem(_entry(f"tomorrow-{index}"), NOW + timedelta(days=1))
        )
    for index in range(5):
        items.append(ReviewItem(_entry(f"later-{index}"), NOW + timedelta(days=2)))
    items.append(ReviewItem(_entry("far"), NOW + timedelta(days=10)))

    plan = build_plan(items, NOW)
    assert len(plan.today) == 3
    assert len(plan.tomorrow) == 3
    assert len(plan.in_three_days) == 3
    assert all(item.mistake.id != "far" for item in plan.in_three_days)
