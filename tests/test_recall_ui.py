"""错题本相似题召回的 UI 链路：进入练习、记录展示与作答信号。"""
from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    MistakeEntry,
    Stage,
)
from mathcoach.memory.sqlite_repo import SQLiteRepository
from mathcoach.recall import RecallStore

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _save_mistake(path: Path) -> None:
    """写入一条函数概念错题。"""
    repository = SQLiteRepository(path)
    try:
        repository.save_mistake(
            MistakeEntry(
                id="m1",
                exercise_id="hs-function-intro-001-e1",
                card_id="hs-function-intro-001",
                stage=Stage.HIGH_SCHOOL,
                course="函数与导数",
                exercise_type=ExerciseKind.CHOICE,
                stem="下列对应关系中，y 是 x 的函数的是（ ）",
                user_answer="y² = x",
                correct_answer="y = x²",
                error_type=ErrorType.CONCEPT,
                max_hint_level=1,
                created_at=datetime.now(timezone.utc),
            )
        )
    finally:
        repository.close()


def test_mistake_book_starts_similar_recall_and_records_signal(
    tmp_path, monkeypatch
) -> None:
    """错题本可发起相似题练习，并记录展示与作答信号。"""
    db = tmp_path / "mathcoach.sqlite3"
    signals = tmp_path / "recall.sqlite3"
    _save_mistake(db)
    monkeypatch.setenv("MATHCOACH_DB", str(db))
    monkeypatch.setenv("MATHCOACH_RECALL_DB", str(signals))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "错题本"
    at.run()

    next(
        button for button in at.button if button.label == "练相似题"
    ).click().run()

    assert not at.exception
    assert any(subheader.value == "相似题练习" for subheader in at.subheader)
    assert any("召回自错题" in caption.value for caption in at.caption)

    store = RecallStore(signals)
    try:
        events = store.list_events()
    finally:
        store.close()
    assert len(events) >= 3
    assert all(event.attempted is False for event in events)
    assert any(event.is_transfer for event in events)

    state = at.session_state["similar_state"]
    question = state.questions[0]
    if question.exercise.kind is ExerciseKind.CHOICE:
        at.radio[0].set_value(question.exercise.answer)
    else:
        at.text_input[0].set_value(question.exercise.answer)
    next(
        button for button in at.button if button.label == "提交答案"
    ).click().run()

    assert not at.exception
    store = RecallStore(signals)
    try:
        events = store.list_events()
    finally:
        store.close()
    attempted = [event for event in events if event.attempted]
    assert attempted
    assert attempted[0].correct is True
