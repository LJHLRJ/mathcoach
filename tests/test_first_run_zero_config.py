"""首次启动：零配置建库、游客模式与可操作错误。"""
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mathcoach.domain.models import (
    Consent,
    ExerciseKind,
    Independence,
    Receipt,
    Stage,
)
from mathcoach.domain.settings import AppSettings
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.memory.sqlite_repo import SQLiteRepository
from mathcoach.ui import first_run
from mathcoach.ui.first_run import (
    FirstRunError,
    initialize_repository,
    initialize_settings,
)

PERSISTENT = Consent(memory=True, mistake_book=True)
GUEST = Consent(memory=False, mistake_book=False)


def _tables(path: Path) -> set[str]:
    with sqlite3.connect(str(path)) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row[0] for row in rows}


def _receipt() -> Receipt:
    return Receipt(
        card_id="hs-function-intro-001",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=12,
        max_hint_level=1,
        goal="搞懂函数",
        independence=Independence.INDEPENDENT,
        created_at=datetime(2026, 11, 21, 12, 0, tzinfo=UTC),
    )


def test_first_run_creates_database_and_required_tables(tmp_path):
    path = tmp_path / "nested" / "mathcoach.sqlite3"

    settings = initialize_settings(PERSISTENT, path)
    repository = initialize_repository(PERSISTENT, path)
    try:
        assert isinstance(repository, SQLiteRepository)
        assert settings == AppSettings()
        assert path.exists()
        assert {
            "receipts",
            "mistakes",
            "review_queue",
            "settings",
        } <= _tables(path)
    finally:
        repository.close()


def test_guest_first_run_stays_in_memory_and_is_usable(tmp_path):
    path = tmp_path / "guest.sqlite3"

    settings = initialize_settings(GUEST, path)
    repository = initialize_repository(GUEST, path)
    try:
        assert isinstance(repository, InMemoryRepository)
        assert settings == AppSettings()
        assert not path.exists()

        repository.save_receipt(_receipt(), exercise_id="hs-001-e1")
        assert len(repository.list_receipts()) == 1
        assert not path.exists()
    finally:
        repository.close()


def test_permission_failure_reports_actionable_error(tmp_path, monkeypatch):
    path = tmp_path / "readonly" / "mathcoach.sqlite3"

    def fail(*_args, **_kwargs):
        raise PermissionError(path.parent)

    monkeypatch.setattr(first_run, "build_repository", fail)

    with pytest.raises(FirstRunError) as excinfo:
        initialize_repository(PERSISTENT, path)

    message = str(excinfo.value)
    assert "无法创建数据目录" in message
    assert "磁盘权限" in message
    assert str(path.parent) in message
    assert isinstance(excinfo.value.__cause__, PermissionError)


def test_sqlite_failure_reports_actionable_error(tmp_path, monkeypatch):
    path = tmp_path / "broken.sqlite3"

    def fail(*_args, **_kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(first_run, "load_settings", fail)

    with pytest.raises(FirstRunError) as excinfo:
        initialize_settings(PERSISTENT, path)

    message = str(excinfo.value)
    assert "无法初始化本地数据库" in message
    assert "占用或损坏" in message
    assert isinstance(excinfo.value.__cause__, sqlite3.OperationalError)


def test_newer_database_schema_reports_upgrade_hint(tmp_path, monkeypatch):
    path = tmp_path / "future.sqlite3"

    def fail(*_args, **_kwargs):
        raise RuntimeError("数据库版本 5 高于当前版本 4")

    monkeypatch.setattr(first_run, "build_repository", fail)

    with pytest.raises(FirstRunError) as excinfo:
        initialize_repository(PERSISTENT, path)

    message = str(excinfo.value)
    assert "数据库版本可能高于当前应用版本" in message
    assert "升级 MathCoach" in message
    assert isinstance(excinfo.value.__cause__, RuntimeError)
