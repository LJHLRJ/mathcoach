"""记忆仓储：重启持久化、游客不落盘、复习状态流转。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.models import (
    ChallengeResult,
    Consent,
    DailyResult,
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    ReviewState,
    Stage,
)
from mathcoach.domain.spaced_repetition import Quality
from mathcoach.memory.repository import (
    InMemoryRepository,
    build_repository,
)
from mathcoach.memory.sqlite_repo import SQLiteRepository

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


def _receipt(identifier: str = "r1") -> Receipt:
    return Receipt(
        card_id="card-1",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=12,
        max_hint_level=1,
        goal="搞懂函数",
        independence=Independence.INDEPENDENT,
        created_at=NOW,
        id=identifier,
    )


def _mistake(identifier: str = "m1", **fields) -> MistakeEntry:
    data = {
        "exercise_id": "hs-001-e1",
        "card_id": "card-1",
        "stage": Stage.HIGH_SCHOOL,
        "course": "函数与导数",
        "exercise_type": ExerciseKind.CHOICE,
        "stem": "题干",
        "user_answer": "错答",
        "correct_answer": "正确",
        "error_type": ErrorType.CONCEPT,
        "max_hint_level": 1,
        "created_at": NOW,
    }
    data.update(fields)
    return MistakeEntry(id=identifier, **data)


def test_sqlite_persists_receipts_mistakes_and_review_queue(tmp_path):
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    repository.save_receipt(_receipt(), exercise_id="hs-001-e1")
    repository.save_mistake(_mistake())
    repository.close()

    reopened = SQLiteRepository(path)
    try:
        receipts = reopened.list_receipts()
        assert len(receipts) == 1
        assert receipts[0].id == "r1"
        mistakes = reopened.list_mistakes()
        assert len(mistakes) == 1
        assert mistakes[0].exercise_id == "hs-001-e1"
        assert mistakes[0].review_state is ReviewState.UNREVIEWED
        items = reopened.list_review_items()
        assert len(items) == 1
        assert items[0].due_at == NOW
    finally:
        reopened.close()


def test_consent_roundtrip(tmp_path):
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    repository.save_consent(Consent(memory=False, mistake_book=True))
    repository.close()

    reopened = SQLiteRepository(path)
    try:
        assert reopened.load_consent() == Consent(memory=False, mistake_book=True)
    finally:
        reopened.close()


def test_save_mistake_upserts_by_exercise(tmp_path):
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    try:
        repository.save_mistake(_mistake("first"))
        repository.save_mistake(
            _mistake("second", user_answer="另一次错答", error_type=ErrorType.CALCULATION)
        )
        entries = repository.list_mistakes()
        assert len(entries) == 1
        assert entries[0].id == "first"
        assert entries[0].user_answer == "另一次错答"
        assert entries[0].error_type is ErrorType.CALCULATION
        assert entries[0].review_state is ReviewState.UNREVIEWED
        assert len(repository.list_review_items()) == 1
    finally:
        repository.close()


def test_two_independent_reviews_master_and_leave_queue(tmp_path):
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    try:
        repository.save_mistake(_mistake())
        first = repository.record_review("hs-001-e1", True, NOW)
        assert first is not None
        assert first.review_state is ReviewState.REVIEWING
        assert first.consecutive_correct == 1

        second = repository.record_review(
            "hs-001-e1", True, NOW + timedelta(days=1)
        )
        assert second is not None
        assert second.review_state is ReviewState.MASTERED
        assert repository.list_review_items() == []
        assert repository.list_mistakes(include_mastered=False) == []
        assert len(repository.list_mistakes()) == 1
    finally:
        repository.close()


def test_guest_repository_never_creates_file(tmp_path):
    path = tmp_path / "guest.sqlite3"
    repository = build_repository(Consent(memory=False, mistake_book=False), path)
    assert isinstance(repository, InMemoryRepository)
    assert not path.exists()

    repository.save_mistake(_mistake())
    assert len(repository.list_mistakes()) == 1
    assert not path.exists()


def test_in_memory_repository_keeps_session_data_only():
    repository = InMemoryRepository()
    repository.save_receipt(_receipt(), exercise_id="hs-001-e1")
    repository.save_mistake(_mistake())
    assert len(repository.list_receipts()) == 1
    assert len(repository.list_review_items()) == 1


def test_daily_result_persists_across_restart(tmp_path):
    path = tmp_path / "mathcoach.sqlite3"
    result = DailyResult(
        date="2026-11-20",
        correct=4,
        total=5,
        duration_s=180,
        completed_at=NOW,
    )
    repository = SQLiteRepository(path)
    repository.save_daily_result(result)
    repository.close()

    reopened = SQLiteRepository(path)
    try:
        assert reopened.get_daily_result("2026-11-20") == result
        assert reopened.get_daily_result("2026-11-21") is None
    finally:
        reopened.close()


def test_challenge_results_persist_and_sort(tmp_path):
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    repository.save_challenge_result(ChallengeResult(5, 10, 200, NOW))
    repository.save_challenge_result(ChallengeResult(8, 10, 250, NOW))
    repository.close()

    reopened = SQLiteRepository(path)
    try:
        best = reopened.list_challenge_results()
        assert [(entry.score, entry.duration_s) for entry in best] == [
            (8, 250),
            (5, 200),
        ]
    finally:
        reopened.close()


def test_in_memory_review_accepts_quality():
    repository = InMemoryRepository()
    repository.save_mistake(_mistake())

    updated = repository.record_review("hs-001-e1", Quality.HINTED, NOW)

    assert updated is not None
    assert updated.review_state is ReviewState.REVIEWING
    assert updated.consecutive_correct == 0
