"""学习闭环：掌握度、练习记录、待复习与下一步建议。"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.content.loader import load_content
from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    MistakeEntry,
    Stage,
)
from mathcoach.domain.receipt import build_receipt
from mathcoach.memory.sqlite_repo import SQLiteRepository
from mathcoach.ui.knowledge_browser import summarize_learning

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def _open_knowledge_page(at) -> None:
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()
    next(
        button
        for button in at.button
        if button.label == "先学习此知识点"
    ).click().run()


def _captions(at) -> list[str]:
    return [caption.value for caption in at.caption]


def _start_quiz(at) -> None:
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()
    at.button[0].click().run()


def _wrong_once(at, answer: str) -> None:
    at.radio[0].set_value(answer)
    at.button[0].click().run()


def _card_objects():
    cards, result = load_content(ROOT / "content", strict=False)
    assert result.ok
    return {card.id: card for card in cards}


def test_not_started_state_suggests_learning_card_and_prerequisite():
    status = summarize_learning(
        mastery=None,
        receipt_count=0,
        mistake_count=0,
        pending_review=0,
        prerequisites=("函数的定义域", "函数的概念"),
    )

    assert status.state == "未开始"
    assert "学习卡片" in status.suggestion
    assert "开始练习此知识点" in status.suggestion
    assert "函数的定义域" in status.suggestion


def test_pending_review_has_priority_over_mastery():
    status = summarize_learning(
        mastery=0.9,
        receipt_count=3,
        mistake_count=1,
        pending_review=2,
    )

    assert status.state == "待复习"
    assert "先复习 2 道待复习错题" in status.suggestion


def test_learning_state_continues_practice():
    status = summarize_learning(
        mastery=0.5,
        receipt_count=1,
        mistake_count=0,
        pending_review=0,
    )

    assert status.state == "学习中"
    assert "继续练习" in status.suggestion


def test_low_mastery_guides_to_prerequisite():
    status = summarize_learning(
        mastery=0.2,
        receipt_count=1,
        mistake_count=0,
        pending_review=0,
        prerequisites=("函数的定义域",),
    )

    assert status.state == "学习中"
    assert "建议先复习「函数的定义域」" in status.suggestion


def test_ready_state_suggests_next_point():
    status = summarize_learning(
        mastery=0.8,
        receipt_count=2,
        mistake_count=0,
        pending_review=0,
    )

    assert status.state == "已熟练"
    assert "下一个知识点" in status.suggestion


def test_knowledge_page_shows_not_started_loop(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "loop-empty.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_knowledge_page(at)

    assert not at.exception
    assert any(
        "学习闭环" in markdown.value for markdown in at.markdown
    )
    captions = _captions(at)
    assert any("掌握度：暂无记录 · 未开始" in value for value in captions)
    assert any(
        "0 张收据 · 0 道错题 · 0 道待复习" in value for value in captions
    )
    assert any("下一步：先看学习卡片" in value for value in captions)


def test_knowledge_page_shows_ready_loop(tmp_path, monkeypatch):
    path = tmp_path / "loop-ready.sqlite3"
    card = _card_objects()["hs-function-intro-001"]
    exercise = card.exercises[0]
    repository = SQLiteRepository(path)
    repository.save_receipt(
        build_receipt(
            card,
            exercise,
            "搞懂函数的概念",
            max_hint_level=1,
            duration_s=8,
        ),
        exercise.id,
    )
    repository.set_mastery(card.id, 0.8, NOW)
    repository.close()
    monkeypatch.setenv("MATHCOACH_DB", str(path))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_knowledge_page(at)

    assert not at.exception
    captions = _captions(at)
    assert any("掌握度：80% · 已熟练" in value for value in captions)
    assert any(
        "1 张收据 · 0 道错题 · 0 道待复习" in value for value in captions
    )
    assert any("下一步：可以继续下一个知识点" in value for value in captions)


def test_knowledge_page_shows_pending_review_loop(tmp_path, monkeypatch):
    path = tmp_path / "loop-review.sqlite3"
    repository = SQLiteRepository(path)
    repository.save_mistake(
        MistakeEntry(
            id="loop-mistake-1",
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
            created_at=NOW,
        )
    )
    repository.close()
    monkeypatch.setenv("MATHCOACH_DB", str(path))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _open_knowledge_page(at)

    assert not at.exception
    captions = _captions(at)
    assert any("待复习" in value for value in captions)
    assert any(
        "0 张收据 · 1 道错题 · 1 道待复习" in value for value in captions
    )
    assert any(
        "下一步：先复习 1 道待复习错题" in value for value in captions
    )


def test_wrapup_shows_learning_loop(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "loop-wrapup.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _start_quiz(at)
    _wrong_once(at, "y² = x")
    at.button[0].click().run()  # 再试一次
    _wrong_once(at, "x = 1")
    next(
        button for button in at.button if button.label == "确认错因"
    ).click().run()
    at.button[0].click().run()  # 再试一次
    _wrong_once(at, "x² + y² = 1")

    assert not at.exception
    assert any(
        "学习闭环" in markdown.value for markdown in at.markdown
    )
    captions = _captions(at)
    assert any("待复习" in value for value in captions)
    assert any("下一步：先复习 1 道待复习错题" in value for value in captions)
