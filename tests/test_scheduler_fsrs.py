"""FSRS 调度接入：默认模式、到期过滤、稳定性持久化、SM-2 fallback。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    MistakeEntry,
    Stage,
)
from mathcoach.domain.spaced_repetition import Quality
from mathcoach.memory.scheduler import build_review_queue, scheduler_mode
from mathcoach.memory.sqlite_repo import SQLiteRepository

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _mistake(identifier: str, card_id: str, due_at: datetime) -> MistakeEntry:
    """构造指定到期时间的错题。"""
    return MistakeEntry(
        id=identifier,
        exercise_id=f"{card_id}-{identifier}",
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错答",
        correct_answer="正确",
        error_type=ErrorType.CONCEPT,
        max_hint_level=1,
        created_at=due_at - timedelta(days=1),
        next_review_at=due_at,
    )


def test_default_mode_is_fsrs(monkeypatch):
    """默认调度模式为 FSRS。"""
    monkeypatch.delenv("MATHCOACH_SCHEDULER", raising=False)

    assert scheduler_mode() == "fsrs"


def test_fsrs_mode_filters_by_next_review_at(tmp_path, monkeypatch):
    """FSRS 队列仅包含已到期条目。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "fsrs")
    repo = SQLiteRepository(tmp_path / "fsrs.db")
    repo.save_mistake(_mistake("due", "c1", NOW - timedelta(days=1)))
    repo.save_mistake(_mistake("future", "c2", NOW + timedelta(days=5)))

    queue = build_review_queue(repo, now=NOW)
    items = [item for group in queue.values() for item in group]

    assert {item.card_id for item in items} == {"c1"}


def test_fsrs_review_persists_stability(tmp_path, monkeypatch):
    """复习后稳定性变化并持久化。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "fsrs")
    repo = SQLiteRepository(tmp_path / "fsrs.db")
    saved = repo.save_mistake(_mistake("m1", "c1", NOW))

    first = repo.record_review(saved.exercise_id, Quality.INDEPENDENT, NOW)
    assert first is not None
    assert first.stability > 0
    assert first.reps == 1

    second = repo.record_review(
        saved.exercise_id, Quality.INDEPENDENT, NOW + timedelta(days=3)
    )
    assert second is not None
    assert second.stability != first.stability
    assert second.reps == 2


def test_fsrs_mode_also_handles_legacy_bool_review(tmp_path, monkeypatch):
    """布尔评分在 FSRS 下同样可用。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "fsrs")
    repo = SQLiteRepository(tmp_path / "fsrs.db")
    saved = repo.save_mistake(_mistake("m1", "c1", NOW))

    updated = repo.record_review(saved.exercise_id, True, NOW)

    assert updated is not None
    assert updated.stability > 0


def test_sm2_fallback_keeps_interval_and_ease(tmp_path, monkeypatch):
    """切到 SM-2 时保留间隔与 ease 语义。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "sm2")
    repo = SQLiteRepository(tmp_path / "sm2.db")
    saved = repo.save_mistake(_mistake("m1", "c1", NOW))

    updated = repo.record_review(saved.exercise_id, Quality.INDEPENDENT, NOW)

    assert updated is not None
    assert updated.interval_days == 3
    assert updated.ease > 2.5
