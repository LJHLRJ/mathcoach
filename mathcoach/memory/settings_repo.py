"""设置仓储：独立 settings 表与学习数据清除，不修改现有 SQLite 仓储。"""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from ..config import db_path as default_db_path
from ..domain.models import Consent

_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""
_CLEAR_TABLES = (
    "review_queue",
    "mistakes",
    "receipts",
    "daily_challenge",
    "challenge_results",
    "mastery",
)


class SettingsStore(Protocol):
    """设置读写与学习数据清除的最小契约。"""

    def get_all(self) -> dict[str, Any]: ...

    def set_many(self, values: Mapping[str, Any]) -> None: ...

    def clear_learning_data(self, *, keep_audit: bool = True) -> dict[str, int]: ...

    def close(self) -> None: ...


class InMemorySettingsStore:
    """游客模式：设置仅存在于当前进程。"""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get_all(self) -> dict[str, Any]:
        return dict(self._values)

    def set_many(self, values: Mapping[str, Any]) -> None:
        self._values.update(values)

    def clear_learning_data(self, *, keep_audit: bool = True) -> dict[str, int]:
        # 游客数据由 InMemoryRepository 持有，设置页会禁用清除入口。
        return {}

    def close(self) -> None:
        return None


class SQLiteSettingsStore:
    """在现有数据库旁维护独立 settings 表的轻量仓储。"""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        with self._lock, self._connection:
            self._connection.execute(_SETTINGS_TABLE)

    def get_all(self) -> dict[str, Any]:
        """返回全部设置 JSON 值；损坏的行会被跳过。"""
        with self._lock:
            rows = self._connection.execute(
                "SELECT key, value FROM settings"
            ).fetchall()
        values: dict[str, Any] = {}
        for row in rows:
            try:
                values[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                continue
        return values

    def set_many(self, values: Mapping[str, Any]) -> None:
        """原子写入一批设置，并刷新 updated_at。"""
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            for key, value in values.items():
                self._connection.execute(
                    """
                    INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, json.dumps(value, ensure_ascii=False), timestamp),
                )

    def clear_learning_data(self, *, keep_audit: bool = True) -> dict[str, int]:
        """删除学习数据表并返回各表删除行数；默认保留审计日志。"""
        counts: dict[str, int] = {}
        with self._lock, self._connection:
            for table in _CLEAR_TABLES:
                try:
                    count = self._connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    self._connection.execute(f"DELETE FROM {table}")
                    counts[table] = int(count)
                except sqlite3.OperationalError:
                    continue
            if not keep_audit:
                try:
                    count = self._connection.execute(
                        "SELECT COUNT(*) FROM audit_log"
                    ).fetchone()[0]
                    self._connection.execute("DELETE FROM audit_log")
                    counts["audit_log"] = int(count)
                except sqlite3.OperationalError:
                    pass
        return counts

    def close(self) -> None:
        """关闭数据库连接。"""
        self._connection.close()


def build_settings_store(
    consent: Consent | None = None, path: Path | str | None = None
) -> SettingsStore:
    """游客模式返回内存设置仓储，否则返回同一数据库上的 SQLite 实现。"""
    consent = consent or Consent()
    if not (consent.memory or consent.mistake_book):
        return InMemorySettingsStore()
    return SQLiteSettingsStore(path or default_db_path())


def load_settings_values(store: SettingsStore) -> dict[str, Any]:
    """读取设置映射。"""
    return store.get_all()


def save_settings_values(store: SettingsStore, values: Mapping[str, Any]) -> None:
    """批量写入设置。"""
    store.set_many(values)
