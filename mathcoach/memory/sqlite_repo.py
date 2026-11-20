"""SQLite 仓储：WAL + busy_timeout，所有写操作由单把锁串行化。"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from ..domain.models import (
    AuditEntry,
    Consent,
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    ReviewItem,
    ReviewState,
    Stage,
)
from .repository import DEFAULT_CONSENT
from .scheduler import next_review

SCHEMA_VERSION = 1

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        display_name TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consent (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        memory INTEGER NOT NULL DEFAULT 1,
        mistake_book INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS receipts (
        id TEXT PRIMARY KEY,
        exercise_id TEXT NOT NULL,
        card_id TEXT NOT NULL,
        stage TEXT NOT NULL,
        course TEXT NOT NULL,
        exercise_type TEXT NOT NULL,
        duration_s INTEGER NOT NULL,
        max_hint_level INTEGER NOT NULL,
        restatement_quality TEXT,
        goal TEXT NOT NULL,
        independence TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mistakes (
        id TEXT PRIMARY KEY,
        exercise_id TEXT NOT NULL UNIQUE,
        card_id TEXT NOT NULL,
        stage TEXT NOT NULL,
        course TEXT NOT NULL,
        exercise_type TEXT NOT NULL,
        stem TEXT NOT NULL,
        user_answer TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        error_type TEXT NOT NULL,
        max_hint_level INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        review_state TEXT NOT NULL,
        review_count INTEGER NOT NULL DEFAULT 0,
        consecutive_correct INTEGER NOT NULL DEFAULT 0,
        receipt_ids TEXT NOT NULL DEFAULT '',
        exercise_snapshot TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mistake_id TEXT NOT NULL,
        due_at TEXT NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_review_pending
    ON review_queue(mistake_id) WHERE completed = 0
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_review_due
    ON review_queue(completed, due_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        op TEXT NOT NULL,
        created_at TEXT NOT NULL,
        result TEXT NOT NULL
    )
    """,
)


def _text(value: datetime) -> str:
    return value.isoformat()


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SQLiteRepository:
    def __init__(
        self, path: Path | str, consent: Consent | None = None
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()
        if consent is not None:
            self.save_consent(consent)

    def _create_schema(self) -> None:
        with self._lock, self._connection:
            for statement in _SCHEMA:
                self._connection.execute(statement)
            row = self._connection.execute(
                "SELECT version FROM schema_version LIMIT 1"
            ).fetchone()
            if row is None:
                self._connection.execute(
                    "INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,)
                )
            elif row["version"] != SCHEMA_VERSION:
                raise RuntimeError(
                    f"数据库版本 {row['version']} 与当前版本 {SCHEMA_VERSION} 不一致"
                )

    def save_consent(self, consent: Consent) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO consent(id, memory, mistake_book) VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    memory = excluded.memory,
                    mistake_book = excluded.mistake_book
                """,
                (int(consent.memory), int(consent.mistake_book)),
            )

    def load_consent(self) -> Consent:
        with self._lock:
            row = self._connection.execute(
                "SELECT memory, mistake_book FROM consent WHERE id = 1"
            ).fetchone()
        if row is None:
            return DEFAULT_CONSENT
        return Consent(memory=bool(row["memory"]), mistake_book=bool(row["mistake_book"]))

    def save_receipt(self, receipt: Receipt, exercise_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO receipts(
                    id, exercise_id, card_id, stage, course, exercise_type,
                    duration_s, max_hint_level, restatement_quality, goal,
                    independence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.id,
                    exercise_id,
                    receipt.card_id,
                    receipt.stage.value,
                    receipt.course,
                    receipt.exercise_type.value,
                    receipt.duration_s,
                    receipt.max_hint_level,
                    receipt.restatement_quality,
                    receipt.goal,
                    receipt.independence.value,
                    _text(receipt.created_at),
                ),
            )

    def list_receipts(self, limit: int | None = 50) -> list[Receipt]:
        query = "SELECT * FROM receipts ORDER BY created_at DESC"
        params: tuple = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [self._to_receipt(row) for row in rows]

    def save_mistake(self, entry: MistakeEntry) -> MistakeEntry:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT id, created_at, receipt_ids FROM mistakes WHERE exercise_id = ?",
                (entry.exercise_id,),
            ).fetchone()
            if row is None:
                stored = entry
                self._connection.execute(
                    """
                    INSERT INTO mistakes(
                        id, exercise_id, card_id, stage, course, exercise_type,
                        stem, user_answer, correct_answer, error_type,
                        max_hint_level, created_at, review_state, review_count,
                        consecutive_correct, receipt_ids, exercise_snapshot
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stored.id,
                        stored.exercise_id,
                        stored.card_id,
                        stored.stage.value,
                        stored.course,
                        stored.exercise_type.value,
                        stored.stem,
                        stored.user_answer,
                        stored.correct_answer,
                        stored.error_type.value,
                        stored.max_hint_level,
                        _text(stored.created_at),
                        stored.review_state.value,
                        stored.review_count,
                        stored.consecutive_correct,
                        ",".join(stored.receipt_ids),
                        json.dumps(stored.exercise_snapshot, ensure_ascii=False),
                    ),
                )
            else:
                stored = replace(
                    entry,
                    id=row["id"],
                    created_at=_datetime(row["created_at"]),
                    review_state=ReviewState.UNREVIEWED,
                    review_count=0,
                    consecutive_correct=0,
                    receipt_ids=tuple(
                        item for item in row["receipt_ids"].split(",") if item
                    ),
                )
                self._connection.execute(
                    """
                    UPDATE mistakes SET
                        user_answer = ?, correct_answer = ?, error_type = ?,
                        max_hint_level = ?, review_state = ?, review_count = ?,
                        consecutive_correct = ?, exercise_snapshot = ?
                    WHERE exercise_id = ?
                    """,
                    (
                        stored.user_answer,
                        stored.correct_answer,
                        stored.error_type.value,
                        stored.max_hint_level,
                        stored.review_state.value,
                        stored.review_count,
                        stored.consecutive_correct,
                        json.dumps(stored.exercise_snapshot, ensure_ascii=False),
                        stored.exercise_id,
                    ),
                )
            self._connection.execute(
                "DELETE FROM review_queue WHERE mistake_id = ?", (stored.id,)
            )
            self._connection.execute(
                "INSERT INTO review_queue(mistake_id, due_at, completed) VALUES (?, ?, 0)",
                (stored.id, _text(stored.created_at)),
            )
        return stored

    def find_mistake(self, exercise_id: str) -> MistakeEntry | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM mistakes WHERE exercise_id = ?", (exercise_id,)
            ).fetchone()
        return self._to_mistake(row) if row is not None else None

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]:
        query = "SELECT * FROM mistakes"
        params: list[object] = []
        if not include_mastered:
            query += " WHERE review_state != ?"
            params.append(ReviewState.MASTERED.value)
        query += " ORDER BY created_at DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._lock:
            rows = self._connection.execute(query, tuple(params)).fetchall()
        return [self._to_mistake(row) for row in rows]

    def record_review(
        self, exercise_id: str, independent: bool, now: datetime
    ) -> MistakeEntry | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM mistakes WHERE exercise_id = ?", (exercise_id,)
            ).fetchone()
            if row is None:
                return None
            entry = self._to_mistake(row)
            state, review_count, streak, due_at = next_review(entry, independent, now)
            self._connection.execute(
                """
                UPDATE mistakes SET
                    review_state = ?, review_count = ?, consecutive_correct = ?
                WHERE exercise_id = ?
                """,
                (state.value, review_count, streak, exercise_id),
            )
            if due_at is None:
                self._connection.execute(
                    "UPDATE review_queue SET completed = 1 "
                    "WHERE mistake_id = ? AND completed = 0",
                    (entry.id,),
                )
            else:
                cursor = self._connection.execute(
                    "UPDATE review_queue SET due_at = ? "
                    "WHERE mistake_id = ? AND completed = 0",
                    (_text(due_at), entry.id),
                )
                if cursor.rowcount == 0:
                    self._connection.execute(
                        "INSERT INTO review_queue(mistake_id, due_at, completed) "
                        "VALUES (?, ?, 0)",
                        (entry.id, _text(due_at)),
                    )
            return replace(
                entry,
                review_state=state,
                review_count=review_count,
                consecutive_correct=streak,
            )

    def list_review_items(self) -> list[ReviewItem]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT m.*, q.due_at AS due_at
                FROM mistakes m
                JOIN review_queue q ON q.mistake_id = m.id
                WHERE q.completed = 0 AND m.review_state != ?
                ORDER BY q.due_at
                """,
                (ReviewState.MASTERED.value,),
            ).fetchall()
        return [
            ReviewItem(mistake=self._to_mistake(row), due_at=_datetime(row["due_at"]))
            for row in rows
        ]

    def record_audit(
        self, op: str, result: str, now: datetime | None = None
    ) -> None:
        timestamp = _text(now or datetime.now(timezone.utc))
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO audit_log(op, created_at, result) VALUES (?, ?, ?)",
                (op, timestamp, result),
            )

    def list_audit(self, limit: int = 50) -> list[AuditEntry]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, op, result, created_at FROM audit_log "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            AuditEntry(
                id=row["id"],
                op=row["op"],
                result=row["result"],
                created_at=_datetime(row["created_at"]),
            )
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _to_receipt(self, row: sqlite3.Row) -> Receipt:
        return Receipt(
            id=row["id"],
            card_id=row["card_id"],
            stage=Stage(row["stage"]),
            course=row["course"],
            exercise_type=ExerciseKind(row["exercise_type"]),
            duration_s=row["duration_s"],
            max_hint_level=row["max_hint_level"],
            restatement_quality=row["restatement_quality"],
            goal=row["goal"],
            independence=Independence(row["independence"]),
            created_at=_datetime(row["created_at"]),
        )

    def _to_mistake(self, row: sqlite3.Row) -> MistakeEntry:
        return MistakeEntry(
            id=row["id"],
            exercise_id=row["exercise_id"],
            card_id=row["card_id"],
            stage=Stage(row["stage"]),
            course=row["course"],
            exercise_type=ExerciseKind(row["exercise_type"]),
            stem=row["stem"],
            user_answer=row["user_answer"],
            correct_answer=row["correct_answer"],
            error_type=ErrorType(row["error_type"]),
            max_hint_level=row["max_hint_level"],
            created_at=_datetime(row["created_at"]),
            review_state=ReviewState(row["review_state"]),
            review_count=row["review_count"],
            consecutive_correct=row["consecutive_correct"],
            receipt_ids=tuple(
                item for item in row["receipt_ids"].split(",") if item
            ),
            exercise_snapshot=json.loads(row["exercise_snapshot"] or "{}"),
        )
