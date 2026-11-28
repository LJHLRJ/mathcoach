"""设置仓储：往返、游客模式与学习数据清除。"""
from datetime import datetime, timezone

from mathcoach.domain.models import (
    Consent,
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    Stage,
)
from mathcoach.memory.settings_repo import (
    InMemorySettingsStore,
    SQLiteSettingsStore,
    build_settings_store,
    load_settings_values,
    save_settings_values,
)
from mathcoach.memory.sqlite_repo import SQLiteRepository

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _receipt() -> Receipt:
    """构造收据样例。"""
    return Receipt(
        card_id="hs-001",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=12,
        max_hint_level=1,
        goal="搞懂函数",
        independence=Independence.INDEPENDENT,
        created_at=NOW,
        exercise_id="ex-1",
    )


def _mistake() -> MistakeEntry:
    """构造错题样例。"""
    return MistakeEntry(
        id="m1",
        exercise_id="ex-1",
        card_id="hs-001",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错答",
        correct_answer="正确",
        error_type=ErrorType.CONCEPT,
        max_hint_level=1,
        created_at=NOW,
    )


def test_sqlite_settings_round_trip(tmp_path):
    """设置值跨连接往返一致。"""
    path = tmp_path / "settings.sqlite3"
    store = SQLiteSettingsStore(path)
    save_settings_values(
        store, {"ai_enabled": True, "daily_review_limit": 6}
    )
    store.close()

    reopened = SQLiteSettingsStore(path)
    try:
        values = load_settings_values(reopened)
    finally:
        reopened.close()

    assert values == {"ai_enabled": True, "daily_review_limit": 6}


def test_guest_settings_use_memory_and_do_not_touch_disk(tmp_path):
    """游客模式使用内存存储且不落盘。"""
    path = tmp_path / "guest.sqlite3"
    store = build_settings_store(
        Consent(memory=False, mistake_book=False), path
    )

    assert isinstance(store, InMemorySettingsStore)
    store.set_many({"daily_review_limit": 4})
    assert store.get_all() == {"daily_review_limit": 4}
    assert not path.exists()


def test_clear_learning_data_keeps_audit(tmp_path):
    """清除学习数据时保留审计日志。"""
    path = tmp_path / "clear.sqlite3"
    repository = SQLiteRepository(path)
    repository.save_receipt(_receipt(), "ex-1")
    repository.save_mistake(_mistake())
    repository.record_audit("seed", "ok")
    store = SQLiteSettingsStore(path)
    try:
        counts = store.clear_learning_data(keep_audit=True)
    finally:
        store.close()

    assert counts["receipts"] == 1
    assert counts["mistakes"] == 1
    assert repository.list_receipts(limit=None) == []
    assert repository.list_mistakes(limit=None) == []
    assert repository.list_review_items() == []
    assert repository.list_audit()
    repository.close()


def test_clear_learning_data_can_purge_audit(tmp_path):
    """可选择同时清空审计日志。"""
    path = tmp_path / "purge.sqlite3"
    repository = SQLiteRepository(path)
    repository.record_audit("seed", "ok")
    store = SQLiteSettingsStore(path)
    try:
        store.clear_learning_data(keep_audit=False)
    finally:
        store.close()

    assert repository.list_audit() == []
    repository.close()


def test_in_memory_settings_store_round_trip():
    """内存设置存储读写往返且清除返回空。"""
    store = InMemorySettingsStore()
    store.set_many({"ai_enabled": True, "daily_review_limit": 3})
    assert store.get_all() == {"ai_enabled": True, "daily_review_limit": 3}
    assert store.clear_learning_data() == {}
    store.close()
