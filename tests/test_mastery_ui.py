"""BKT 掌握概率：依据文字、观察更新与仪表盘展示。"""
from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.basis import basis_for_mastery
from mathcoach.domain.models import ErrorType, ExerciseKind, MistakeEntry, Stage
from mathcoach.memory.sqlite_repo import SQLiteRepository

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def test_basis_for_mastery_uses_probability():
    """掌握依据包含概率百分比。"""
    text = basis_for_mastery(6, 1, 3, probability=0.62)

    assert "掌握概率" in text
    assert "62%" in text


def test_mastery_observation_updates_probability(tmp_path):
    """正确观察提升掌握概率并持久化。"""
    repo = SQLiteRepository(tmp_path / "mastery.db")
    repo.set_mastery("hs-001", 0.3, NOW)

    updated = repo.record_mastery("hs-001", correct=True, now=NOW)

    assert updated > 0.3
    assert repo.get_mastery("hs-001") == updated


def test_dashboard_shows_bkt_probability(tmp_path, monkeypatch):
    """仪表盘展示 BKT 掌握概率。"""
    path = tmp_path / "mathcoach.sqlite3"
    repo = SQLiteRepository(path)
    repo.save_mistake(
        MistakeEntry(
            id="m1",
            exercise_id="hs-001-e1",
            card_id="hs-001",
            stage=Stage.HIGH_SCHOOL,
            course="函数与导数",
            exercise_type=ExerciseKind.CHOICE,
            stem="题干",
            user_answer="错",
            correct_answer="A",
            error_type=ErrorType.CONCEPT,
            max_hint_level=1,
            created_at=NOW,
        )
    )
    # 直接设定概率，避免 seed 错题时的 BKT 观察干扰断言
    repo.set_mastery("hs-001", 0.62, NOW)
    repo.close()

    monkeypatch.setenv("MATHCOACH_DB", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[1].select("仪表盘").run()

    assert not at.exception
    assert any("62%" in caption.value for caption in at.caption)
