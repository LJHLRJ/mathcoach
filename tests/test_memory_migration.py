"""schema v1→v2 迁移：现有 db 打开后自动补齐三列，数据不丢。"""
import sqlite3

from mathcoach.memory.sqlite_repo import SCHEMA_VERSION, SQLiteRepository


def test_fresh_db_has_schema_v2(tmp_path):
    repo = SQLiteRepository(tmp_path / "fresh.db")
    with sqlite3.connect(repo.db_path) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        cols = {row[1] for row in conn.execute("PRAGMA table_info(mistakes)")}
    assert version == SCHEMA_VERSION
    assert {"ease", "interval_days", "next_review_at"} <= cols


def test_v1_db_migrates_and_keeps_rows(tmp_path):
    db_path = tmp_path / "v1.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL);
            INSERT INTO schema_version VALUES (1);
            CREATE TABLE mistakes (
                id TEXT PRIMARY KEY, card_id TEXT NOT NULL, error_type TEXT NOT NULL,
                created_at TEXT NOT NULL, review_state TEXT NOT NULL, review_count INTEGER DEFAULT 0
            );
            INSERT INTO mistakes VALUES ('m1', 'hs-001', '概念不清', '2026-11-01T00:00:00+00:00', '未复习', 0);
            """
        )
    repo = SQLiteRepository(db_path)
    with sqlite3.connect(repo.db_path) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        row = conn.execute(
            "SELECT ease, interval_days, next_review_at FROM mistakes WHERE id='m1'"
        ).fetchone()
    assert version == SCHEMA_VERSION
    assert row[0] == 2.5
    assert row[1] == 1
    assert row[2] is not None
