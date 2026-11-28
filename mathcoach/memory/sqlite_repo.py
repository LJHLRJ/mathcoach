"""SQLite 仓储：WAL + busy_timeout，所有写操作由单把锁串行化。"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from ..domain.bkt import bkt_params, initial_mastery, update_mastery
from ..domain.fsrs import (
    MemoryState,
    Rating,
    initial_state,
    interval_from_retrievability,
    review as fsrs_review,
)
from ..domain.models import (
    AuditEntry,
    ChallengeResult,
    Consent,
    DailyResult,
    ErrorType,
    ExerciseKind,
    Independence,
    MasterySnapshot,
    MistakeEntry,
    Receipt,
    ReviewItem,
    ReviewState,
    Stage,
)
from ..domain.spaced_repetition import (
    Quality,
    quality_from_independence,
    quality_from_outcome,
    update_schedule,
)
from .repository import DEFAULT_CONSENT
from .scheduler import fsrs_params, next_review, scheduler_mode

SCHEMA_VERSION = 4

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
    """
    CREATE TABLE IF NOT EXISTS daily_challenge (
        date TEXT PRIMARY KEY,
        correct INTEGER NOT NULL,
        total INTEGER NOT NULL,
        duration_s INTEGER NOT NULL,
        completed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS challenge_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        score INTEGER NOT NULL,
        total INTEGER NOT NULL,
        duration_s INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
)


# 迁移脚本按版本号登记；1 号就是现有 v1 建表脚本，2 号只追加列，不改历史列
_MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: _SCHEMA,
    2: (
        "ALTER TABLE mistakes ADD COLUMN ease REAL NOT NULL DEFAULT 2.5",
        "ALTER TABLE mistakes ADD COLUMN interval_days INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE mistakes ADD COLUMN next_review_at TEXT NOT NULL "
        "DEFAULT '1970-01-01T00:00:00+00:00'",
    ),
    3: (
        # FSRS 状态；stability=0 表示旧数据尚未初始化，由调度器首次评分时补齐
        "ALTER TABLE mistakes ADD COLUMN stability REAL NOT NULL DEFAULT 0.0",
        "ALTER TABLE mistakes ADD COLUMN difficulty REAL NOT NULL DEFAULT 5.0",
        "ALTER TABLE mistakes ADD COLUMN reps INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE mistakes ADD COLUMN lapses INTEGER NOT NULL DEFAULT 0",
    ),
    4: (
        # BKT 掌握概率按 card_id 独立存储，不改动 mistakes 历史列
        """
        CREATE TABLE IF NOT EXISTS mastery (
            card_id TEXT PRIMARY KEY,
            probability REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    ),
}

# 纯增量表：旧库已停在当前版本，用 IF NOT EXISTS 在每次打开时补齐；
# 首次升级时把现有 mastery 行回填成一条历史快照
_ADDITIVE_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS mastery_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id TEXT NOT NULL,
        probability REAL NOT NULL,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_mastery_history_card_time
    ON mastery_history(card_id, recorded_at)
    """,
    """
    INSERT INTO mastery_history(card_id, probability, recorded_at)
    SELECT mastery.card_id, mastery.probability, mastery.updated_at
    FROM mastery
    WHERE NOT EXISTS (
        SELECT 1 FROM mastery_history
        WHERE mastery_history.card_id = mastery.card_id
    )
    """,
)


def _migrate(connection: sqlite3.Connection, from_version: int) -> None:
    """从 from_version 逐级迁移到 SCHEMA_VERSION。"""
    for version in range(from_version + 1, SCHEMA_VERSION + 1):
        for statement in _MIGRATIONS[version]:
            connection.execute(statement)
        connection.execute("UPDATE schema_version SET version = ?", (version,))


def _text(value: datetime) -> str:
    """时间转 ISO 字符串。"""
    return value.isoformat()


def _datetime(value: str) -> datetime:
    """ISO 字符串转时间。"""
    return datetime.fromisoformat(value)


def _rating_for_quality(quality: Quality) -> Rating:
    """把三档 Quality 映射到 FSRS 四档 Rating。"""
    if quality is Quality.WRONG:
        return Rating.AGAIN
    if quality is Quality.HINTED:
        return Rating.HARD
    return Rating.GOOD


class SQLiteRepository:
    """SQLite 实现；WAL、busy_timeout 5 秒，写操作由单把锁串行化。

    Attributes:
        path: 数据库文件路径。
        db_path: 路径的字符串形式，供外部按路径检查。
    """

    def __init__(
        self, path: Path | str, consent: Consent | None = None
    ) -> None:
        """打开数据库，建表并按需迁移；传入 consent 时立即写入。"""
        self.path = Path(path)
        self.db_path = str(self.path)  # 兼容迁移测试与外部按路径检查 schema
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
        """建表、初始化版本号并按需迁移。"""
        with self._lock, self._connection:
            # v1 建表脚本全部使用 IF NOT EXISTS，可安全用于全新库和旧库
            for statement in _SCHEMA:
                self._connection.execute(statement)
            row = self._connection.execute(
                "SELECT version FROM schema_version LIMIT 1"
            ).fetchone()
            if row is None:
                self._connection.execute(
                    "INSERT INTO schema_version(version) VALUES (1)"
                )
                _migrate(self._connection, 1)
            elif row["version"] < SCHEMA_VERSION:
                _migrate(self._connection, row["version"])
            elif row["version"] > SCHEMA_VERSION:
                raise RuntimeError(
                    f"数据库版本 {row['version']} 高于当前版本 {SCHEMA_VERSION}"
                )
            for statement in _ADDITIVE_SCHEMA:
                self._connection.execute(statement)

    def save_consent(self, consent: Consent) -> None:
        """保存授权状态。"""
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
        """读取授权状态；没有记录时返回默认值。"""
        with self._lock:
            row = self._connection.execute(
                "SELECT memory, mistake_book FROM consent WHERE id = 1"
            ).fetchone()
        if row is None:
            return DEFAULT_CONSENT
        return Consent(memory=bool(row["memory"]), mistake_book=bool(row["mistake_book"]))

    def get_mastery(self, card_id: str) -> float | None:
        """读取掌握概率；没有记录时返回 None。"""
        with self._lock:
            row = self._connection.execute(
                "SELECT probability FROM mastery WHERE card_id = ?", (card_id,)
            ).fetchone()
        return float(row["probability"]) if row is not None else None

    def list_mastery_history(
        self, card_id: str | None = None
    ) -> list[MasterySnapshot]:
        """按记录时间升序返回掌握度快照；可按卡片过滤。"""
        query = (
            "SELECT card_id, probability, recorded_at FROM mastery_history"
        )
        params: tuple = ()
        if card_id is not None:
            query += " WHERE card_id = ?"
            params = (card_id,)
        query += " ORDER BY recorded_at ASC, id ASC"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [
            MasterySnapshot(
                card_id=row["card_id"],
                probability=float(row["probability"]),
                recorded_at=_datetime(row["recorded_at"]),
            )
            for row in rows
        ]

    def set_mastery(self, card_id: str, probability: float, now: datetime) -> None:
        """写入掌握概率，截到 [0, 1]，并追加一条历史快照。"""
        value = max(0.0, min(1.0, float(probability)))
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO mastery(card_id, probability, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    probability = excluded.probability,
                    updated_at = excluded.updated_at
                """,
                (card_id, value, _text(now)),
            )
            self._connection.execute(
                """
                INSERT INTO mastery_history(card_id, probability, recorded_at)
                VALUES (?, ?, ?)
                """,
                (card_id, value, _text(now)),
            )

    def record_mastery(
        self,
        card_id: str,
        correct: bool,
        now: datetime,
        quality: Quality | None = None,
        *,
        mastery_weight: float = 1.0,
    ) -> float:
        """按一次作答更新 BKT 掌握概率并返回新值。

        ``mastery_weight`` 只缩放本次更新幅度，公式本身不变。
        """
        prior = self.get_mastery(card_id)
        if prior is None:
            prior = initial_mastery(bkt_params())
        updated = update_mastery(prior, correct, bkt_params(), quality=quality)
        weight = max(0.0, min(1.0, float(mastery_weight)))
        if weight < 1.0:
            updated = prior + weight * (updated - prior)
        self.set_mastery(card_id, updated, now)
        return updated

    def save_receipt(
        self,
        receipt: Receipt,
        exercise_id: str,
        *,
        mastery_weight: float = 1.0,
    ) -> None:
        """写入或替换收据，并推进掌握概率。"""
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
        # 收据代表一次通过观察，按提示层级折减后同步推进 BKT 掌握概率
        quality = quality_from_outcome(True, receipt.max_hint_level)
        self.record_mastery(
            receipt.card_id,
            correct=True,
            now=receipt.created_at,
            quality=quality,
            mastery_weight=mastery_weight,
        )

    def update_receipt_restatement(
        self, receipt_id: str, quality: str
    ) -> bool:
        """只补写 L6 复述质量，不重复推进掌握概率。"""
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE receipts SET restatement_quality = ? WHERE id = ?",
                (quality, receipt_id),
            )
        return cursor.rowcount > 0

    def list_receipts(self, limit: int | None = 50) -> list[Receipt]:
        """按创建时间倒序返回收据；``limit=None`` 返回全部。"""
        query = "SELECT * FROM receipts ORDER BY created_at DESC"
        params: tuple = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [self._to_receipt(row) for row in rows]

    def save_mistake(self, entry: MistakeEntry) -> MistakeEntry:
        """写入错题；同题已存在时保留 id 与创建时间、重置复习进度，并把队列重置到创建时间。"""
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
                        consecutive_correct, receipt_ids, exercise_snapshot,
                        ease, interval_days, next_review_at,
                        stability, difficulty, reps, lapses
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        stored.ease,
                        stored.interval_days,
                        _text(stored.next_review_at or stored.created_at),
                        stored.stability,
                        stored.difficulty,
                        stored.reps,
                        stored.lapses,
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
        # 错题代表一次未通过观察，同步推进 BKT 掌握概率
        self.record_mastery(stored.card_id, correct=False, now=stored.created_at)
        return stored

    def find_mistake(self, exercise_id: str) -> MistakeEntry | None:
        """按题目 ID 取错题。"""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM mistakes WHERE exercise_id = ?", (exercise_id,)
            ).fetchone()
        return self._to_mistake(row) if row is not None else None

    def update_mistake_error_type(
        self, exercise_id: str, error_type: ErrorType
    ) -> MistakeEntry | None:
        """只更新错因，不改变复习进度与掌握概率。"""
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM mistakes WHERE exercise_id = ?", (exercise_id,)
            ).fetchone()
            if row is None:
                return None
            entry = self._to_mistake(row)
            self._connection.execute(
                "UPDATE mistakes SET error_type = ? WHERE exercise_id = ?",
                (error_type.value, exercise_id),
            )
        return replace(entry, error_type=error_type)

    def add_mistake(self, card_id: str, error_type: str, now: datetime) -> str:
        """测试与内部迁移用的最小错题写入，返回错题 id。"""
        identifier = uuid4().hex
        entry = MistakeEntry(
            id=identifier,
            exercise_id=f"{card_id}-{identifier}",  # 保证 exercise_id 唯一
            card_id=card_id,
            stage=Stage.HIGH_SCHOOL,
            course="",
            exercise_type=ExerciseKind.CHOICE,
            stem="",
            user_answer="",
            correct_answer="",
            error_type=ErrorType(error_type),
            max_hint_level=0,
            created_at=now,
            next_review_at=now,  # 新错题立即可复习
        )
        self.save_mistake(entry)
        return identifier

    def get_mistake(self, mistake_id: str) -> MistakeEntry | None:
        """按错题 id 取错题。"""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM mistakes WHERE id = ?", (mistake_id,)
            ).fetchone()
        return self._to_mistake(row) if row is not None else None

    def list_due_mistakes(self, now: datetime) -> list[MistakeEntry]:
        """按 SM-2 的 next_review_at 过滤到期错题，已掌握的不再返回。"""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM mistakes WHERE next_review_at <= ? "
                "AND review_state != ? ORDER BY next_review_at",
                (_text(now), ReviewState.MASTERED.value),
            ).fetchall()
        return [self._to_mistake(row) for row in rows]

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]:
        """按创建时间倒序返回错题，可含或排除已掌握。"""
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
        self, exercise_id: str, independent: bool | Quality, now: datetime
    ) -> MistakeEntry | None:
        """登记一次复习。

        先把 bool 或 ``Quality`` 统一成评分，再按 ``MATHCOACH_SCHEDULER``
        选择 FSRS 或 SM-2 路径；只更新复习状态与到期时间，掌握概率由上层
        按本次作答单独记录。

        Args:
            exercise_id: 题目 ID。
            independent: 是否独立完成，或直接给 ``Quality``。
            now: 复习时间。

        Returns:
            更新后的错题；题目不存在时为 None。
        """
        # bool 与 Quality 两种调用都映射到统一评分，再按环境变量选择调度器
        if isinstance(independent, Quality):
            quality = independent
        else:
            quality = quality_from_independence(independent)

        if scheduler_mode() == "sm2":
            result = self.record_sm2_review(exercise_id, quality, now)
        else:
            result = self.record_fsrs_review(exercise_id, quality, now)
        return result

    def record_fsrs_review(
        self, exercise_id: str, quality: Quality, now: datetime
    ) -> MistakeEntry | None:
        """按 FSRS 更新稳定性/难度/间隔，同时保留旧状态机的掌握计数。"""
        params = fsrs_params()
        rating = _rating_for_quality(quality)
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM mistakes WHERE exercise_id = ?", (exercise_id,)
            ).fetchone()
            if row is None:
                return None
            entry = self._to_mistake(row)
            if entry.stability <= 0:
                # 旧数据首次评分：用当前评分初始化，不猜测历史
                state = initial_state(rating, params)
                interval = interval_from_retrievability(
                    state.stability,
                    params.desired_retention,
                    params.max_interval_days,
                )
            else:
                # 用“到期日 - 上次间隔”还原上次复习时间，避免到期当天复习被算成 0 天
                anchor = (
                    entry.next_review_at - timedelta(days=entry.interval_days)
                    if entry.next_review_at
                    else entry.created_at
                )
                elapsed_days = max(0.0, (now - anchor).total_seconds() / 86400)
                state, interval = fsrs_review(
                    MemoryState(
                        stability=entry.stability,
                        difficulty=entry.difficulty,
                        reps=entry.reps,
                        lapses=entry.lapses,
                    ),
                    rating,
                    elapsed_days,
                    params,
                )
            # 掌握状态和连续独立次数仍由旧状态机决定，FSRS 只管间隔
            review_state, review_count, streak, _ = next_review(
                entry, quality is Quality.INDEPENDENT, now
            )
            due_at = now + timedelta(days=interval)
            self._connection.execute(
                """
                UPDATE mistakes SET
                    stability = ?, difficulty = ?, reps = ?, lapses = ?,
                    interval_days = ?, next_review_at = ?,
                    review_state = ?, review_count = ?, consecutive_correct = ?
                WHERE exercise_id = ?
                """,
                (
                    state.stability,
                    state.difficulty,
                    state.reps,
                    state.lapses,
                    interval,
                    _text(due_at),
                    review_state.value,
                    review_count,
                    streak,
                    exercise_id,
                ),
            )
            if review_state is ReviewState.MASTERED:
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
                stability=state.stability,
                difficulty=state.difficulty,
                reps=state.reps,
                lapses=state.lapses,
                interval_days=interval,
                next_review_at=due_at,
                review_state=review_state,
                review_count=review_count,
                consecutive_correct=streak,
            )

    def record_sm2_review(
        self, mistake_id: str, quality: Quality, now: datetime
    ) -> MistakeEntry | None:
        """按 SM-2 更新难度因子与间隔，并同步旧状态机的掌握计数。"""
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM mistakes WHERE id = ? OR exercise_id = ?",
                (mistake_id, mistake_id),
            ).fetchone()
            if row is None:
                return None
            entry = self._to_mistake(row)
            schedule = update_schedule(
                entry.ease, entry.interval_days, quality, now
            )
            review_state, review_count, streak, _ = next_review(
                entry, quality is Quality.INDEPENDENT, now
            )
            self._connection.execute(
                """
                UPDATE mistakes SET ease = ?, interval_days = ?, next_review_at = ?,
                    review_state = ?, review_count = ?, consecutive_correct = ?
                WHERE id = ?
                """,
                (
                    schedule.ease,
                    schedule.interval_days,
                    _text(schedule.next_review_at),
                    review_state.value,
                    review_count,
                    streak,
                    entry.id,
                ),
            )
            if review_state is ReviewState.MASTERED:
                self._connection.execute(
                    "UPDATE review_queue SET completed = 1 "
                    "WHERE mistake_id = ? AND completed = 0",
                    (entry.id,),
                )
            else:
                # 同步旧复习队列，避免复习清单与 SM-2 到期时间分叉
                cursor = self._connection.execute(
                    "UPDATE review_queue SET due_at = ? "
                    "WHERE mistake_id = ? AND completed = 0",
                    (_text(schedule.next_review_at), entry.id),
                )
                if cursor.rowcount == 0:
                    self._connection.execute(
                        "INSERT INTO review_queue(mistake_id, due_at, completed) "
                        "VALUES (?, ?, 0)",
                        (entry.id, _text(schedule.next_review_at)),
                    )
            return replace(
                entry,
                ease=schedule.ease,
                interval_days=schedule.interval_days,
                next_review_at=schedule.next_review_at,
                review_state=review_state,
                review_count=review_count,
                consecutive_correct=streak,
            )

    def list_review_items(self) -> list[ReviewItem]:
        """返回未掌握且未完成的复习项，按到期时间排序。"""
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
        """追加一条审计记录。"""
        timestamp = _text(now or datetime.now(timezone.utc))
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO audit_log(op, created_at, result) VALUES (?, ?, ?)",
                (op, timestamp, result),
            )

    def list_audit(self, limit: int = 50) -> list[AuditEntry]:
        """按时间倒序返回审计记录。"""
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

    def save_daily_result(self, result: DailyResult) -> None:
        """按日期键保存每日挑战结果。"""
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO daily_challenge(
                    date, correct, total, duration_s, completed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    result.date,
                    result.correct,
                    result.total,
                    result.duration_s,
                    _text(result.completed_at),
                ),
            )

    def get_daily_result(self, day: str) -> DailyResult | None:
        """按日期键取每日挑战结果。"""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM daily_challenge WHERE date = ?", (day,)
            ).fetchone()
        if row is None:
            return None
        return DailyResult(
            date=row["date"],
            correct=row["correct"],
            total=row["total"],
            duration_s=row["duration_s"],
            completed_at=_datetime(row["completed_at"]),
        )

    def save_challenge_result(self, result: ChallengeResult) -> ChallengeResult:
        """保存挑战赛成绩，返回带自增 id 的结果。"""
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO challenge_results(score, total, duration_s, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    result.score,
                    result.total,
                    result.duration_s,
                    _text(result.created_at),
                ),
            )
            result_id = int(cursor.lastrowid)
        return replace(result, id=result_id)

    def list_challenge_results(self, limit: int = 10) -> list[ChallengeResult]:
        """按分数降序、用时升序返回挑战成绩。"""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM challenge_results "
                "ORDER BY score DESC, duration_s ASC, id ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            ChallengeResult(
                id=row["id"],
                score=row["score"],
                total=row["total"],
                duration_s=row["duration_s"],
                created_at=_datetime(row["created_at"]),
            )
            for row in rows
        ]

    def close(self) -> None:
        """关闭数据库连接。"""
        with self._lock:
            self._connection.close()

    def _to_receipt(self, row: sqlite3.Row) -> Receipt:
        """把查询行转成收据。"""
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
            exercise_id=row["exercise_id"],
        )

    def _to_mistake(self, row: sqlite3.Row) -> MistakeEntry:
        """把查询行转成错题。"""
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
            ease=row["ease"],
            interval_days=row["interval_days"],
            next_review_at=(
                _datetime(row["next_review_at"]) if row["next_review_at"] else None
            ),
            stability=row["stability"],
            difficulty=row["difficulty"],
            reps=row["reps"],
            lapses=row["lapses"],
        )
