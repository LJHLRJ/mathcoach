"""schema v2→v3 迁移：mistakes 增加 FSRS 四列，旧数据不丢。"""
import sqlite3

from mathcoach.memory.sqlite_repo import _MIGRATIONS, SCHEMA_VERSION, SQLiteRepository


def test_fresh_db_has_schema_v3_and_fsrs_columns(tmp_path):
    repo = SQLiteRepository(tmp_path / "fresh.db")

    with sqlite3.connect(repo.db_path) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        cols = {row[1] for row in conn.execute("PRAGMA table_info(mistakes)")}

    assert SCHEMA_VERSION == 3
    assert version == 3
    assert {"stability", "difficulty", "reps", "lapses"} <= cols


def test_v2_db_migrates_keeps_rows_and_sets_defaults(tmp_path):
    db_path = tmp_path / "v2.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL);
            INSERT INTO schema_version VALUES (2);
            CREATE TABLE mistakes (
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
                exercise_snapshot TEXT NOT NULL DEFAULT '{}',
                ease REAL NOT NULL DEFAULT 2.5,
                interval_days INTEGER NOT NULL DEFAULT 1,
                next_review_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00+00:00'
            );
            INSERT INTO mistakes(
                id, exercise_id, card_id, stage, course, exercise_type, stem,
                user_answer, correct_answer, error_type, max_hint_level,
                created_at, review_state, review_count, consecutive_correct,
                receipt_ids, exercise_snapshot, ease, interval_days, next_review_at
            ) VALUES (
                'm1', 'ex1', 'hs-001', '高中', '函数', 'choice', '题干',
                'A', 'B', '概念不清', 1,
                '2026-11-01T00:00:00+00:00', '复习中', 2, 1,
                'r1', '{}', 2.7, 5, '2026-11-10T00:00:00+00:00'
            );
            """
        )

    repo = SQLiteRepository(db_path)

    with sqlite3.connect(repo.db_path) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        row = conn.execute(
            "SELECT id, stem, ease, interval_days, stability, difficulty, reps, lapses "
            "FROM mistakes WHERE id = 'm1'"
        ).fetchone()

    assert version == 3
    assert row[0] == "m1"
    assert row[1] == "题干"
    assert row[2] == 2.7
    assert row[3] == 5
    assert row[4:] == (0.0, 5.0, 0, 0)


def test_v3_migration_only_adds_columns():
    statements = _MIGRATIONS[3]

    assert len(statements) == 4
    for statement in statements:
        upper = statement.upper()
        assert upper.startswith("ALTER TABLE MISTAKES ADD COLUMN")
        assert "DROP " not in upper
        assert "DELETE " not in upper
        assert "UPDATE " not in upper
