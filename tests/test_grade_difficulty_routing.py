"""按年级页面：路由可调用、筛选、记忆与今日复习跨年级。"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    MistakeEntry,
    Stage,
)
from mathcoach.memory.sqlite_repo import SQLiteRepository

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def _select_mode(at, label: str) -> None:
    next(
        box for box in at.selectbox if box.label == "功能"
    ).select(label).run()


def _open_grade_page(at) -> None:
    _select_mode(at, "按年级")


def _selectbox(at, label: str):
    return next(box for box in at.selectbox if box.label == label)


def test_grade_page_renders_and_filters(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "grade-page.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_grade_page(at)

    assert not at.exception
    assert at.subheader[0].value == "按年级"
    grade = _selectbox(at, "年级")
    assert grade.value == "all"

    grade.select("mixed").run()
    assert not at.exception
    assert any(
        "共 122 张卡片" in caption.value for caption in at.caption
    )

    difficulty = _selectbox(at, "难度")
    difficulty.select("basic").run()
    assert any(
        "共 46 张卡片" in caption.value for caption in at.caption
    )

    grade = _selectbox(at, "年级")
    grade.select("g1").run()
    assert any(
        "共 0 张卡片" in caption.value for caption in at.caption
    )
    assert any(
        "该年级/难度暂无卡片" in info.value for info in at.info
    )


def test_grade_selection_persists_across_modes(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "grade-memory.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_grade_page(at)
    _selectbox(at, "年级").select("mixed").run()

    _select_mode(at, "仪表盘")
    _select_mode(at, "按年级")

    assert not at.exception
    assert _selectbox(at, "年级").value == "mixed"


def test_today_review_counts_all_stages(tmp_path, monkeypatch):
    path = tmp_path / "grade-review.sqlite3"
    repository = SQLiteRepository(path)
    for index, (stage, course, card_id) in enumerate(
        [
            (Stage.HIGH_SCHOOL, "函数与导数", "hs-function-intro-001"),
            (Stage.GRADUATE, "泛函分析", "grad-functional-001"),
        ]
    ):
        repository.save_mistake(
            MistakeEntry(
                id=f"grade-mistake-{index}",
                exercise_id=f"{card_id}-e1",
                card_id=card_id,
                stage=stage,
                course=course,
                exercise_type=ExerciseKind.CHOICE,
                stem=f"跨年级错题 {index}",
                user_answer="错",
                correct_answer="对",
                error_type=ErrorType.CONCEPT,
                max_hint_level=1,
                created_at=NOW,
            )
        )
    repository.close()
    monkeypatch.setenv("MATHCOACH_DB", str(path))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_grade_page(at)

    assert not at.exception
    metric = next(
        item
        for item in at.metric
        if item.label == "今日待复习（跨年级）"
    )
    assert metric.value == "2"
