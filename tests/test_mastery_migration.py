"""schema v3→v4：新增 mastery 表，旧数据不丢，读写接口可用。"""
import sqlite3
from datetime import datetime, timezone

from mathcoach.memory.sqlite_repo import SCHEMA_VERSION, SQLiteRepository

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def test_fresh_db_has_schema_v4_and_mastery_table(tmp_path):
    repo = SQLiteRepository(tmp_path / "fresh.db")

    with sqlite3.connect(repo.db_path) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        columns = {row[1] for row in conn.execute("PRAGMA table_info(mastery)")}

    assert SCHEMA_VERSION == 4
    assert version == 4
    assert {"card_id", "probability", "updated_at"} <= columns


def test_v3_db_migrates_keeps_mistakes_and_adds_mastery(tmp_path):
    db_path = tmp_path / "v3.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL);
            INSERT INTO schema_version VALUES (3);
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
        mistake = conn.execute("SELECT id, card_id FROM mistakes WHERE id='m1'").fetchone()
        mastery_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(mastery)")
        }

    assert version == 4
    assert mistake == ("m1", "hs-001")
    assert {"card_id", "probability", "updated_at"} <= mastery_columns


def test_get_and_set_mastery_roundtrip(tmp_path):
    repo = SQLiteRepository(tmp_path / "mastery.db")

    assert repo.get_mastery("hs-001") is None

    repo.set_mastery("hs-001", 0.62, NOW)
    assert repo.get_mastery("hs-001") == 0.62

    repo.set_mastery("hs-001", 0.81, NOW)
    assert repo.get_mastery("hs-001") == 0.81


def test_existing_mastery_is_backfilled_into_history(tmp_path):
    db_path = tmp_path / "backfill.db"
    repository = SQLiteRepository(db_path)
    repository.set_mastery("hs-001", 0.62, NOW)
    repository.close()

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM mastery_history")

    reopened = SQLiteRepository(db_path)
    try:
        history = reopened.list_mastery_history("hs-001")
        assert len(history) == 1
        assert history[0].probability == 0.62
    finally:
        reopened.close()
