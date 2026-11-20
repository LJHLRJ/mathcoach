"""审计日志：只记录操作类型、时间与结果，不写学习数据或 Token。"""
from datetime import datetime, timezone

from mathcoach.memory.repository import InMemoryRepository
from mathcoach.memory.sqlite_repo import SQLiteRepository

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


def test_sqlite_audit_log_persists(tmp_path):
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    repository.record_audit("receipt", "ok", NOW)
    repository.record_audit("goal", "blocked:instruction", NOW)
    repository.close()

    reopened = SQLiteRepository(path)
    try:
        entries = reopened.list_audit()
        assert len(entries) == 2
        assert entries[0].op == "goal"
        assert entries[0].result == "blocked:instruction"
        assert entries[1].op == "receipt"
    finally:
        reopened.close()


def test_in_memory_audit_log_keeps_short_history():
    repository = InMemoryRepository()
    for index in range(5):
        repository.record_audit(f"op-{index}", "ok", NOW)
    entries = repository.list_audit(limit=2)
    assert [entry.op for entry in entries] == ["op-4", "op-3"]
