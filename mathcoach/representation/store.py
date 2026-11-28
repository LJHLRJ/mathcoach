"""表示降级信号：独立 SQLite 表，记录降级决策与下一次作答结果。

不写正式学习档案，也不参与 BKT/FSRS 更新。
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..config import db_path
from ..domain.representation import Representation
from .models import RepresentationEvent, RepresentationRecorder

REPRESENTATION_DB_ENV = "MATHCOACH_REPRESENTATION_DB"
REPRESENTATION_DB_NAME = "representation-signals.sqlite3"
REPRESENTATION_TABLE = "representation_events"
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {REPRESENTATION_TABLE} (
    id TEXT PRIMARY KEY,
    exercise_id TEXT NOT NULL,
    card_id TEXT NOT NULL,
    kc_id TEXT NOT NULL DEFAULT '',
    from_repr TEXT NOT NULL,
    to_repr TEXT NOT NULL,
    triggers TEXT NOT NULL DEFAULT '[]',
    shown_at TEXT NOT NULL,
    resolved_at TEXT,
    next_correct INTEGER,
    next_hint_level INTEGER
)
"""


def representation_db_path() -> Path:
    """返回表示信号库路径；默认与正式库同目录。"""
    override = os.getenv(REPRESENTATION_DB_ENV)
    if override:
        return Path(override)
    return db_path().with_name(REPRESENTATION_DB_NAME)


def _bool_to_int(value: bool | None) -> int | None:
    """三态布尔转 SQLite 整数。"""
    if value is None:
        return None
    return 1 if value else 0


def _int_to_bool(value: object) -> bool | None:
    """SQLite 整数转三态布尔。"""
    if value is None:
        return None
    return bool(value)


class RepresentationStore:
    """降级事件与结果的 SQLite 存储。"""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = (
            Path(path) if path is not None else representation_db_path()
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.path), check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def record(self, event: RepresentationEvent) -> str:
        """写入一条降级事件并返回事件 ID。"""
        with self._connection:
            self._connection.execute(
                f"""
                INSERT INTO {REPRESENTATION_TABLE}(
                    id, exercise_id, card_id, kc_id, from_repr, to_repr,
                    triggers, shown_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.exercise_id,
                    event.card_id,
                    event.kc_id,
                    event.from_repr.value,
                    event.to_repr.value,
                    json.dumps(list(event.triggers), ensure_ascii=False),
                    event.shown_at.isoformat(),
                ),
            )
        return event.id

    def record_outcome(
        self,
        event_id: str,
        *,
        correct: bool | None,
        hint_level: int,
        now: datetime | None = None,
    ) -> bool:
        """回填降级后的第一次作答；事件不存在时返回 False。"""
        moment = now or datetime.now(timezone.utc)
        with self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE {REPRESENTATION_TABLE}
                SET resolved_at = ?, next_correct = ?, next_hint_level = ?
                WHERE id = ?
                """,
                (
                    moment.isoformat(),
                    _bool_to_int(correct),
                    int(hint_level),
                    event_id,
                ),
            )
        return cursor.rowcount > 0

    def list_events(self, limit: int = 100) -> list[RepresentationEvent]:
        """按展示时间倒序返回降级事件。"""
        rows = self._connection.execute(
            f"""
            SELECT * FROM {REPRESENTATION_TABLE}
            ORDER BY shown_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            RepresentationEvent(
                id=row["id"],
                exercise_id=row["exercise_id"],
                card_id=row["card_id"],
                kc_id=row["kc_id"],
                from_repr=Representation(row["from_repr"]),
                to_repr=Representation(row["to_repr"]),
                triggers=tuple(json.loads(row["triggers"])),
                shown_at=datetime.fromisoformat(row["shown_at"]),
                resolved_at=(
                    datetime.fromisoformat(row["resolved_at"])
                    if row["resolved_at"]
                    else None
                ),
                next_correct=_int_to_bool(row["next_correct"]),
                next_hint_level=row["next_hint_level"],
            )
            for row in rows
        ]

    def close(self) -> None:
        """关闭数据库连接。"""
        self._connection.close()

    def __enter__(self) -> RepresentationStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class RepresentationStoreRecorder:
    """短连接记录器；异常交给会话引擎降级处理。"""

    def record(self, event: RepresentationEvent) -> str:
        """写入一条降级事件。"""
        with RepresentationStore() as store:
            return store.record(event)

    def record_outcome(
        self, event_id: str, *, correct: bool | None, hint_level: int
    ) -> None:
        """回填降级后的第一次作答。"""
        with RepresentationStore() as store:
            store.record_outcome(
                event_id, correct=correct, hint_level=hint_level
            )


def as_recorder(store: RepresentationStore) -> RepresentationRecorder:
    """把存储适配成记录器协议，便于测试注入同一连接。"""
    return _StoreRecorderAdapter(store)


class _StoreRecorderAdapter:
    """复用已有 store 连接的轻量适配器。"""

    def __init__(self, store: RepresentationStore) -> None:
        self._store = store

    def record(self, event: RepresentationEvent) -> str:
        return self._store.record(event)

    def record_outcome(
        self, event_id: str, *, correct: bool | None, hint_level: int
    ) -> None:
        self._store.record_outcome(
            event_id, correct=correct, hint_level=hint_level
        )
