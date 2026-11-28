"""召回效果信号：独立 SQLite 表，记录展示与作答结果。

不写正式学习档案，也不参与 BKT/FSRS 更新。
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..config import db_path
from .similar import SimilarCandidate

RECALL_DB_ENV = "MATHCOACH_RECALL_DB"
RECALL_DB_NAME = "recall-signals.sqlite3"
RECALL_TABLE = "recall_events"
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {RECALL_TABLE} (
    id TEXT PRIMARY KEY,
    source_exercise_id TEXT NOT NULL,
    candidate_exercise_id TEXT NOT NULL,
    is_transfer INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    shown_at TEXT NOT NULL,
    attempted INTEGER NOT NULL DEFAULT 0,
    correct INTEGER
)
"""


def recall_db_path() -> Path:
    """返回召回信号库路径；默认与正式库同目录。"""
    override = os.getenv(RECALL_DB_ENV)
    if override:
        return Path(override)
    return db_path().with_name(RECALL_DB_NAME)


@dataclass(frozen=True)
class RecallEvent:
    """一条召回展示记录。"""

    id: str
    source_exercise_id: str
    candidate_exercise_id: str
    is_transfer: bool
    rank: int
    score: float
    shown_at: datetime
    attempted: bool
    correct: bool | None


class RecallStore:
    """召回展示与结果的 SQLite 存储。"""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else recall_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.path), check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def record_impression(
        self,
        source_exercise_id: str,
        candidates: list[SimilarCandidate],
        now: datetime | None = None,
    ) -> dict[str, str]:
        """登记一次召回展示，返回候选题目 ID 到记录 ID 的映射。"""
        moment = now or datetime.now(timezone.utc)
        mapping: dict[str, str] = {}
        with self._connection:
            for rank, candidate in enumerate(candidates, start=1):
                identifier = uuid4().hex
                self._connection.execute(
                    f"""
                    INSERT INTO {RECALL_TABLE}(
                        id, source_exercise_id, candidate_exercise_id,
                        is_transfer, rank, score, shown_at, attempted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        identifier,
                        source_exercise_id,
                        candidate.exercise.id,
                        int(candidate.is_transfer),
                        rank,
                        candidate.score,
                        moment.isoformat(),
                    ),
                )
                mapping[candidate.exercise.id] = identifier
        return mapping

    def record_outcome(
        self,
        impression_id: str,
        correct: bool | None,
        now: datetime | None = None,
    ) -> bool:
        """登记一次作答结果；``None`` 表示已尝试但无法自动判分。"""
        value = None if correct is None else int(correct)
        with self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE {RECALL_TABLE}
                SET attempted = 1, correct = ?
                WHERE id = ?
                """,
                (value, impression_id),
            )
        return cursor.rowcount > 0

    def list_events(self, limit: int = 100) -> list[RecallEvent]:
        """按展示时间倒序返回召回记录。"""
        rows = self._connection.execute(
            f"""
            SELECT * FROM {RECALL_TABLE}
            ORDER BY shown_at DESC, rank ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            RecallEvent(
                id=row["id"],
                source_exercise_id=row["source_exercise_id"],
                candidate_exercise_id=row["candidate_exercise_id"],
                is_transfer=bool(row["is_transfer"]),
                rank=row["rank"],
                score=row["score"],
                shown_at=datetime.fromisoformat(row["shown_at"]),
                attempted=bool(row["attempted"]),
                correct=(
                    None if row["correct"] is None else bool(row["correct"])
                ),
            )
            for row in rows
        ]

    def close(self) -> None:
        """关闭数据库连接。"""
        self._connection.close()

    def __enter__(self) -> RecallStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
