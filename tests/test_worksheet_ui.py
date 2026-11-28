"""可打印练习单 UI：模式入口、当前卡片与错题来源。"""
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

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_worksheet_mode_uses_current_card(tmp_path, monkeypatch) -> None:
    """默认按当前卡片生成练习单并提供下载。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[0].select("hs-function-intro-001").run()
    at.selectbox[1].select("可打印练习单").run()

    assert not at.exception
    assert any(
        subheader.value == "可打印练习单" for subheader in at.subheader
    )
    markdown = " ".join(item.value for item in at.markdown)
    assert "当前卡片：函数的概念" in markdown
    assert "下列对应关系中" in markdown
    assert any(
        button.label == "下载可打印 HTML" for button in at.download_button
    )

    next(
        radio for radio in at.radio if radio.label == "题目来源"
    ).set_value("同章节/同课程多卡").run()

    assert not at.exception
    markdown = " ".join(item.value for item in at.markdown)
    assert "同章节/同课程：函数的概念" in markdown
    assert "f(x)=1/(x−1)" in markdown


def test_worksheet_mode_can_use_mistake_book(tmp_path, monkeypatch) -> None:
    """错题本来源可生成含该错题的练习单。"""
    db = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(db)
    try:
        repository.save_mistake(
            MistakeEntry(
                id="m-trig",
                exercise_id="hs-trig-002-e2",
                card_id="hs-trig-002",
                stage=Stage.HIGH_SCHOOL,
                course="三角函数",
                exercise_type=ExerciseKind.FILL,
                stem="若 sin x=3/5 且 x 在第一象限，则 cos x=（ ）",
                user_answer="−4/5",
                correct_answer="4/5",
                error_type=ErrorType.CONCEPT,
                max_hint_level=1,
                created_at=datetime.now(timezone.utc),
            )
        )
    finally:
        repository.close()
    monkeypatch.setenv("MATHCOACH_DB", str(db))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[1].select("可打印练习单").run()
    next(
        radio for radio in at.radio if radio.label == "题目来源"
    ).set_value("错题本").run()

    assert not at.exception
    markdown = " ".join(item.value for item in at.markdown)
    assert "错题本" in markdown
    assert "若 sin x=3/5" in markdown
