"""追问效果信号：独立 SQLite 表，记录命中/降级与学生回答。

不写正式学习档案，也不参与 BKT/FSRS 或错题复习更新。
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from ...config import db_path
from ...safety.redlines import sanitize_text
from .models import DialogEvent, DialogEventKind

DIALOG_DB_ENV = "MATHCOACH_DIALOG_DB"
DIALOG_DB_NAME = "dialog-signals.sqlite3"
DIALOG_TABLE = "dialog_events"
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {DIALOG_TABLE} (
    id TEXT PRIMARY KEY,
    exercise_id TEXT NOT NULL,
    card_id TEXT NOT NULL,
    kc_ids TEXT NOT NULL,
    level INTEGER NOT NULL,
    supplement INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    downgraded INTEGER NOT NULL,
    answer TEXT NOT NULL,
    reason TEXT NOT NULL,
    shown_at TEXT NOT NULL,
    resolved_at TEXT NOT NULL
)
"""


def dialog_db_path() -> Path:
    """返回追问信号库路径；默认与正式库同目录。"""
    override = os.getenv(DIALOG_DB_ENV)
    if override:
        return Path(override)
    return db_path().with_name(DIALOG_DB_NAME)


class DialogStore:
    """追问事件的 SQLite 存储。"""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else dialog_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.path), check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def record(self, event: DialogEvent) -> str:
        """写入一条追问事件，返回事件 ID。"""
        with self._connection:
            self._connection.execute(
                f"""
                INSERT INTO {DIALOG_TABLE}(
                    id, exercise_id, card_id, kc_ids, level, supplement,
                    outcome, downgraded, answer, reason,
                    shown_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.exercise_id,
                    event.card_id,
                    json.dumps(list(event.kc_ids), ensure_ascii=False),
                    event.level,
                    int(event.supplement),
                    event.kind.value,
                    int(event.downgraded),
                    sanitize_text(event.answer),
                    sanitize_text(event.reason),
                    event.shown_at.isoformat(),
                    event.resolved_at.isoformat(),
                ),
            )
        return event.id

    def list_events(self, limit: int = 100) -> list[DialogEvent]:
        """按解决时间倒序返回追问事件。"""
        rows = self._connection.execute(
            f"""
            SELECT * FROM {DIALOG_TABLE}
            ORDER BY resolved_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            DialogEvent(
                id=row["id"],
                exercise_id=row["exercise_id"],
                card_id=row["card_id"],
                kc_ids=tuple(json.loads(row["kc_ids"])),
                level=row["level"],
                supplement=bool(row["supplement"]),
                kind=DialogEventKind(row["outcome"]),
                downgraded=bool(row["downgraded"]),
                answer=row["answer"],
                reason=row["reason"],
                shown_at=datetime.fromisoformat(row["shown_at"]),
                resolved_at=datetime.fromisoformat(row["resolved_at"]),
            )
            for row in rows
        ]

    def close(self) -> None:
        """关闭数据库连接。"""
        self._connection.close()

    def __enter__(self) -> DialogStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
