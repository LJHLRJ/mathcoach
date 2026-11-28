"""记忆仓储：重启持久化、游客不落盘、复习状态流转。"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from mathcoach.domain.bkt import initial_mastery
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
    """构造收据样例。"""
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
    """构造错题样例。"""
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
    """SQLite 跨重启保留收据、错题与复习队列。"""
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


def test_receipt_restatement_updates_without_extra_mastery(tmp_path):
    """复述更新不额外提升掌握度。"""
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    receipt = _receipt()
    repository.save_receipt(receipt, exercise_id="hs-001-e1")
    before = repository.get_mastery(receipt.card_id)
    assert repository.update_receipt_restatement(receipt.id, "完整") is True
    repository.close()

    reopened = SQLiteRepository(path)
    try:
        assert reopened.list_receipts()[0].restatement_quality == "完整"
        assert reopened.get_mastery(receipt.card_id) == before
    finally:
        reopened.close()


def test_hinted_receipt_gains_less_mastery(tmp_path):
    """有提示收据的掌握度增益更小。"""
    repository = SQLiteRepository(tmp_path / "mathcoach.sqlite3")
    try:
        repository.save_receipt(_receipt("r-independent"), exercise_id="e1")
        repository.save_receipt(
            replace(
                _receipt("r-hinted"),
                card_id="card-2",
                max_hint_level=4,
                independence=Independence.SEMI_INDEPENDENT,
            ),
            exercise_id="e2",
        )

        independent = repository.get_mastery("card-1")
        hinted = repository.get_mastery("card-2")
        assert independent is not None and hinted is not None
        assert independent > hinted > initial_mastery()
    finally:
        repository.close()


def test_consent_roundtrip(tmp_path):
    """同意状态往返一致。"""
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
    """错题按练习号覆盖更新。"""
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
    """两次独立复习后掌握并离开队列。"""
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
    """游客仓储不创建文件。"""
    path = tmp_path / "guest.sqlite3"
    repository = build_repository(Consent(memory=False, mistake_book=False), path)
    assert isinstance(repository, InMemoryRepository)
    assert not path.exists()

    repository.save_mistake(_mistake())
    assert len(repository.list_mistakes()) == 1
    assert not path.exists()


def test_in_memory_repository_keeps_session_data_only():
    """内存仓储保留会话内数据。"""
    repository = InMemoryRepository()
    repository.save_receipt(_receipt(), exercise_id="hs-001-e1")
    repository.save_mistake(_mistake())
    assert len(repository.list_receipts()) == 1
    assert len(repository.list_review_items()) == 1


def test_daily_result_persists_across_restart(tmp_path):
    """每日结果跨重启保留。"""
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
    """挑战结果持久化并按成绩排序。"""
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
    """内存仓储接受评分档位。"""
    repository = InMemoryRepository()
    repository.save_mistake(_mistake())

    updated = repository.record_review("hs-001-e1", Quality.HINTED, NOW)

    assert updated is not None
    assert updated.review_state is ReviewState.REVIEWING
    assert updated.consecutive_correct == 0


def test_review_does_not_double_count_mastery(tmp_path):
    """内存与 SQLite 掌握度计算一致。"""
    memory = InMemoryRepository()
    memory.save_mistake(_mistake())
    memory.record_review("hs-001-e1", True, NOW)

    disk = SQLiteRepository(tmp_path / "mastery.db")
    try:
        disk.save_mistake(_mistake())
        disk.record_review("hs-001-e1", True, NOW)
        assert memory.get_mastery("card-1") == disk.get_mastery("card-1")
    finally:
        disk.close()


def test_mastery_history_persists(tmp_path):
    """掌握度历史持久化并保序。"""
    path = tmp_path / "mastery-history.sqlite3"
    repository = SQLiteRepository(path)
    repository.set_mastery("card-1", 0.4, NOW - timedelta(days=1))
    repository.set_mastery("card-1", 0.6, NOW)
    repository.close()

    reopened = SQLiteRepository(path)
    try:
        history = reopened.list_mastery_history("card-1")
        assert [round(item.probability, 2) for item in history] == [0.4, 0.6]
        assert history[0].recorded_at < history[1].recorded_at
        assert reopened.list_mastery_history("card-2") == []
    finally:
        reopened.close()


def test_in_memory_mastery_history_appends_updates():
    """内存掌握度历史追加更新。"""
    repository = InMemoryRepository()
    repository.set_mastery("card-1", 0.4, NOW)
    repository.record_mastery("card-1", True, NOW + timedelta(days=1))

    history = repository.list_mastery_history("card-1")

    assert len(history) == 2
    assert history[0].probability == 0.4
    assert history[-1].probability > 0.4


def test_update_error_type_keeps_review_progress(tmp_path):
    """修改错因保留复习进度。"""
    repository = SQLiteRepository(tmp_path / "error-type.db")
    try:
        repository.save_mistake(_mistake())
        repository.record_review("hs-001-e1", True, NOW)
        before = repository.find_mistake("hs-001-e1")

        updated = repository.update_mistake_error_type(
            "hs-001-e1", ErrorType.FORMULA
        )

        assert updated is not None
        assert updated.error_type is ErrorType.FORMULA
        assert updated.review_state is before.review_state
        assert updated.review_count == before.review_count
    finally:
        repository.close()
