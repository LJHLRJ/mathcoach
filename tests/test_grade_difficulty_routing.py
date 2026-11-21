"""按年级页面：路由可调用、筛选、记忆与今日复习跨年级。"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import (
    Consent,
    ErrorType,
    ExerciseKind,
    MistakeEntry,
    Stage,
)
from mathcoach.memory.settings_repo import SQLiteSettingsStore
from mathcoach.memory.sqlite_repo import SQLiteRepository
from mathcoach.ui.grade_page import (
    load_default_grade,
    save_default_grade,
)

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
PERSISTENT = Consent(memory=True, mistake_book=True)


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


def test_difficulty_groups_and_learning_entry(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "grade-groups.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_grade_page(at)
    _selectbox(at, "年级").select("mixed").run()

    assert not at.exception
    expanders = {item.label for item in at.expander}
    assert "先学习本年级知识点" in expanders
    assert "基础 · 46 张卡片" in expanders
    assert "进阶 · 47 张卡片" in expanders
    assert "挑战 · 29 张卡片" in expanders

    _selectbox(at, "难度").select("basic").run()
    assert _selectbox(at, "年级").value == "mixed"

    knowledge = _selectbox(at, "选择知识点")
    knowledge.select("hs-function-intro-001").run()
    next(
        button for button in at.button if button.label == "打开学习卡片"
    ).click().run()

    assert not at.exception
    assert at.subheader[0].value == "知识点浏览"
    assert any(
        "函数的概念" in markdown.value for markdown in at.markdown
    )


def test_empty_grade_learning_entry(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "grade-empty-entry.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_grade_page(at)
    _selectbox(at, "年级").select("g1").run()

    assert not at.exception
    assert any(
        "该年级暂无已标注知识点" in caption.value
        for caption in at.caption
    )


def test_default_grade_persists_in_settings_store(tmp_path):
    path = tmp_path / "grade-default.sqlite3"

    assert load_default_grade(PERSISTENT, path) == "all"
    assert save_default_grade(PERSISTENT, "mixed", path) is True
    assert load_default_grade(PERSISTENT, path) == "mixed"
    assert save_default_grade(PERSISTENT, "unknown", path) is False
    assert load_default_grade(PERSISTENT, path) == "mixed"


def test_default_grade_applied_to_grade_page(tmp_path, monkeypatch):
    path = tmp_path / "grade-default-ui.sqlite3"
    store = SQLiteSettingsStore(path)
    try:
        store.set_many({"default_grade": "mixed"})
    finally:
        store.close()
    monkeypatch.setenv("MATHCOACH_DB", str(path))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_grade_page(at)

    assert not at.exception
    assert _selectbox(at, "年级").value == "mixed"


def test_settings_page_shows_default_grade_control(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "grade-settings.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    assert any(
        box.label == "默认进入年级" for box in at.selectbox
    )
    assert any(
        button.label == "保存学习入口设置" for button in at.button
    )
