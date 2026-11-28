"""步骤信号存储：独立 SQLite，不写正式学习档案。"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..config import db_path
from ..safety.redlines import sanitize_text
from .models import StepAttempt, StepRun, StepVerdict

STEP_DB_ENV = "MATHCOACH_STEP_DB"
STEP_DB_NAME = "step-signals.sqlite3"
STEP_RUNS_TABLE = "step_runs"
STEP_ATTEMPTS_TABLE = "step_attempts"
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {STEP_RUNS_TABLE} (
    id TEXT PRIMARY KEY,
    exercise_id TEXT NOT NULL,
    card_id TEXT NOT NULL,
    kc_ids TEXT NOT NULL,
    mode TEXT NOT NULL,
    step_count INTEGER NOT NULL DEFAULT 0,
    failed_step_index INTEGER,
    missing_steps TEXT NOT NULL DEFAULT '[]',
    final_answer TEXT NOT NULL DEFAULT '',
    final_correct INTEGER,
    mismatch INTEGER NOT NULL DEFAULT 0,
    abandoned INTEGER NOT NULL DEFAULT 0,
    kc_applied INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS {STEP_ATTEMPTS_TABLE} (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    exercise_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    input TEXT NOT NULL,
    verdict TEXT NOT NULL,
    expected TEXT NOT NULL,
    kc_id TEXT NOT NULL DEFAULT '',
    step_tag TEXT NOT NULL DEFAULT '',
    elapsed_s REAL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, step_index)
);
CREATE INDEX IF NOT EXISTS idx_step_runs_exercise
    ON {STEP_RUNS_TABLE}(exercise_id, created_at);
"""


def step_db_path() -> Path:
    """返回步骤库路径；默认与正式库同目录，文件名独立。"""
    override = os.getenv(STEP_DB_ENV)
    if override:
        return Path(override)
    return db_path().with_name(STEP_DB_NAME)


def _bool_to_int(value: bool | None) -> int | None:
    """三态布尔转 SQLite 整数。"""
    if value is None:
        return None
    return 1 if value else 0


def _int_to_bool(value: object) -> bool | None:
    """SQLite 整数转回三态布尔。"""
    if value is None:
        return None
    return bool(int(value))


class StepStore:
    """步骤运行与逐步作答的 SQLite 存储。"""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else step_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.path), check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.executescript(_SCHEMA)
        self._migrate()
        self._connection.commit()

    def _migrate(self) -> None:
        """为旧版步骤库补上耗时/缺失/放弃字段。"""
        columns = {
            str(row["name"])
            for row in self._connection.execute(
                f"PRAGMA table_info({STEP_RUNS_TABLE})"
            )
        }
        additions = {
            "step_count": "INTEGER NOT NULL DEFAULT 0",
            "missing_steps": "TEXT NOT NULL DEFAULT '[]'",
            "abandoned": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in additions.items():
            if name not in columns:
                self._connection.execute(
                    f"ALTER TABLE {STEP_RUNS_TABLE} "
                    f"ADD COLUMN {name} {definition}"
                )

    def save_run(self, run: StepRun) -> str:
        """写入或覆盖一条步骤运行。"""
        with self._connection:
            self._connection.execute(
                f"""
                INSERT INTO {STEP_RUNS_TABLE}(
                    id, exercise_id, card_id, kc_ids, mode, step_count,
                    failed_step_index, missing_steps, final_answer,
                    final_correct, mismatch, abandoned, kc_applied,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kc_ids = excluded.kc_ids,
                    mode = excluded.mode,
                    step_count = excluded.step_count,
                    failed_step_index = excluded.failed_step_index,
                    missing_steps = excluded.missing_steps,
                    final_answer = excluded.final_answer,
                    final_correct = excluded.final_correct,
                    mismatch = excluded.mismatch,
                    abandoned = excluded.abandoned,
                    kc_applied = excluded.kc_applied,
                    updated_at = excluded.updated_at
                """,
                (
                    run.id,
                    run.exercise_id,
                    run.card_id,
                    json.dumps(list(run.kc_ids), ensure_ascii=False),
                    run.mode,
                    run.step_count,
                    run.failed_step_index,
                    json.dumps(list(run.missing_steps)),
                    sanitize_text(run.final_answer),
                    _bool_to_int(run.final_correct),
                    int(run.mismatch),
                    int(run.abandoned),
                    int(run.kc_applied),
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )
        return run.id

    def add_attempt(self, attempt: StepAttempt) -> str:
        """写入或覆盖一条步骤作答。"""
        with self._connection:
            self._connection.execute(
                f"""
                INSERT INTO {STEP_ATTEMPTS_TABLE}(
                    id, run_id, exercise_id, step_index, input, verdict,
                    expected, kc_id, step_tag, elapsed_s, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, step_index) DO UPDATE SET
                    id = excluded.id,
                    input = excluded.input,
                    verdict = excluded.verdict,
                    expected = excluded.expected,
                    kc_id = excluded.kc_id,
                    step_tag = excluded.step_tag,
                    elapsed_s = excluded.elapsed_s,
                    created_at = excluded.created_at
                """,
                (
                    attempt.id,
                    attempt.run_id,
                    attempt.exercise_id,
                    attempt.step_index,
                    sanitize_text(attempt.input),
                    attempt.verdict.value,
                    attempt.expected,
                    attempt.kc_id,
                    attempt.step_tag,
                    attempt.elapsed_s,
                    attempt.created_at.isoformat(),
                ),
            )
        return attempt.id

    def finalize_run(
        self,
        run_id: str,
        *,
        final_answer: str,
        final_correct: bool | None,
        failed_step_index: int | None,
        mismatch: bool,
        kc_applied: bool,
        missing_steps: tuple[int, ...] = (),
        abandoned: bool = False,
        now: datetime | None = None,
    ) -> None:
        """补写最终答案与归因结果。"""
        moment = (now or datetime.now(timezone.utc)).isoformat()
        with self._connection:
            self._connection.execute(
                f"""
                UPDATE {STEP_RUNS_TABLE}
                SET final_answer = ?, final_correct = ?,
                    failed_step_index = ?, mismatch = ?,
                    missing_steps = ?, abandoned = ?,
                    kc_applied = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    sanitize_text(final_answer),
                    _bool_to_int(final_correct),
                    failed_step_index,
                    int(mismatch),
                    json.dumps(list(missing_steps)),
                    int(abandoned),
                    int(kc_applied),
                    moment,
                    run_id,
                ),
            )

    def get_run(self, run_id: str) -> StepRun | None:
        """按 ID 读取一条步骤运行及其全部作答。"""
        row = self._connection.execute(
            f"SELECT * FROM {STEP_RUNS_TABLE} WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        attempts = self._connection.execute(
            f"""
            SELECT * FROM {STEP_ATTEMPTS_TABLE}
            WHERE run_id = ? ORDER BY step_index
            """,
            (run_id,),
        ).fetchall()
        return _run_from_row(row, attempts)

    def list_pending(self, exercise_id: str) -> list[StepRun]:
        """返回某题尚未结算且未放弃的步骤运行。"""
        rows = self._connection.execute(
            f"""
            SELECT * FROM {STEP_RUNS_TABLE}
            WHERE exercise_id = ? AND abandoned = 0
              AND final_answer = '' AND final_correct IS NULL
            ORDER BY created_at
            """,
            (exercise_id,),
        ).fetchall()
        runs: list[StepRun] = []
        for row in rows:
            attempts = self._connection.execute(
                f"""
                SELECT * FROM {STEP_ATTEMPTS_TABLE}
                WHERE run_id = ? ORDER BY step_index
                """,
                (row["id"],),
            ).fetchall()
            runs.append(_run_from_row(row, attempts))
        return runs

    def list_runs(self, limit: int = 100) -> list[StepRun]:
        """按创建时间倒序返回步骤运行。"""
        rows = self._connection.execute(
            f"""
            SELECT * FROM {STEP_RUNS_TABLE}
            ORDER BY created_at DESC LIMIT ?
            """,
            (max(0, int(limit)),),
        ).fetchall()
        runs: list[StepRun] = []
        for row in rows:
            attempts = self._connection.execute(
                f"""
                SELECT * FROM {STEP_ATTEMPTS_TABLE}
                WHERE run_id = ? ORDER BY step_index
                """,
                (row["id"],),
            ).fetchall()
            runs.append(_run_from_row(row, attempts))
        return runs

    def close(self) -> None:
        """关闭数据库连接。"""
        self._connection.close()

    def __enter__(self) -> StepStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _run_from_row(
    row: sqlite3.Row, attempts: list[sqlite3.Row]
) -> StepRun:
    """把查询结果还原成 ``StepRun``。"""
    return StepRun(
        id=str(row["id"]),
        exercise_id=str(row["exercise_id"]),
        card_id=str(row["card_id"]),
        kc_ids=tuple(json.loads(row["kc_ids"] or "[]")),
        mode=str(row["mode"]),
        step_count=int(row["step_count"] or 0),
        failed_step_index=row["failed_step_index"],
        missing_steps=tuple(
            json.loads(row["missing_steps"] or "[]")
        ),
        final_answer=str(row["final_answer"] or ""),
        final_correct=_int_to_bool(row["final_correct"]),
        mismatch=bool(row["mismatch"]),
        abandoned=bool(row["abandoned"]),
        kc_applied=bool(row["kc_applied"]),
        attempts=tuple(_attempt_from_row(item) for item in attempts),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _attempt_from_row(row: sqlite3.Row) -> StepAttempt:
    """把查询结果还原成 ``StepAttempt``。"""
    return StepAttempt(
        id=str(row["id"]),
        run_id=str(row["run_id"]),
        exercise_id=str(row["exercise_id"]),
        step_index=int(row["step_index"]),
        input=str(row["input"]),
        verdict=StepVerdict(row["verdict"]),
        expected=str(row["expected"]),
        kc_id=str(row["kc_id"] or ""),
        step_tag=str(row["step_tag"] or ""),
        elapsed_s=row["elapsed_s"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
