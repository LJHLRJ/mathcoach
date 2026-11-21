"""解析展示与错因定位：知识点、先修链、建议与答题页渲染。"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mathcoach.content.loader import load_content
from mathcoach.domain.explanation import (
    build_explanation,
    locate_error,
)
from mathcoach.domain.knowledge_tree import load_knowledge_tree
from mathcoach.domain.models import ErrorType

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content"
TREE_PATH = CONTENT_ROOT / "knowledge_tree.yaml"
APP_PATH = ROOT / "app.py"


@pytest.fixture(scope="module")
def cards_by_id():
    cards, result = load_content(CONTENT_ROOT, strict=False)
    assert result.ok
    return {card.id: card for card in cards}


@pytest.fixture(scope="module")
def tree():
    return load_knowledge_tree(TREE_PATH)


def _exercise(card, suffix: str):
    return next(
        exercise for exercise in card.exercises if exercise.id.endswith(suffix)
    )


def _text(at) -> str:
    return " ".join(
        [element.value for element in at.markdown]
        + [element.value for element in at.caption]
    )


def _start_quiz(at) -> None:
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()
    at.button[0].click().run()


def _wrong_once(at, answer: str) -> None:
    at.radio[0].set_value(answer)
    at.button[0].click().run()


def test_explanation_combines_exercise_and_knowledge_point(
    cards_by_id, tree
):
    card = cards_by_id["hs-func-003"]
    exercise = _exercise(card, "e1")

    explanation = build_explanation(card, exercise, tree)

    assert explanation.knowledge_point_id == "hs-func-003"
    assert explanation.knowledge_point_name == "函数的单调性"
    assert explanation.course == "函数与导数"
    assert explanation.answer == "单调递增"
    assert explanation.solution_outline == exercise.solution_outline
    assert explanation.common_mistakes == card.mistakes
    assert [item.name for item in explanation.prerequisites] == [
        "函数的定义域",
        "函数的概念",
    ]


def test_explanation_falls_back_to_card_without_tree(cards_by_id):
    card = cards_by_id["hs-func-003"]
    exercise = _exercise(card, "e1")

    explanation = build_explanation(card, exercise)

    assert explanation.knowledge_point_name == card.name
    assert explanation.course == card.course
    assert explanation.prerequisites == ()


def test_concept_error_points_to_nearest_prerequisite(cards_by_id, tree):
    card = cards_by_id["hs-func-003"]

    localization = locate_error(card, ErrorType.CONCEPT, tree)

    assert localization.review_id == "hs-func-002"
    assert localization.review_name == "函数的定义域"
    assert "先补齐先修概念" in localization.suggestion
    assert localization.reason == "概念或前提还没理清"
    assert [item.id for item in localization.prerequisites] == [
        "hs-func-002",
        "hs-function-intro-001",
    ]


def test_error_without_prerequisites_reviews_current_point(cards_by_id, tree):
    card = cards_by_id["hs-function-intro-001"]

    localization = locate_error(card, ErrorType.CONCEPT, tree)

    assert localization.review_id == card.id
    assert localization.review_name == "函数的概念"
    assert "复述" in localization.suggestion


def test_calculation_error_keeps_current_knowledge_point(cards_by_id, tree):
    card = cards_by_id["hs-func-003"]

    localization = locate_error(card, ErrorType.CALCULATION, tree)

    assert localization.review_id == card.id
    assert "复算" in localization.suggestion


def test_explicit_reason_overrides_default(cards_by_id, tree):
    card = cards_by_id["hs-function-intro-001"]

    localization = locate_error(
        card,
        ErrorType.READING,
        tree,
        reason="看错了不等号方向",
    )

    assert localization.reason == "看错了不等号方向"


def test_hint_page_shows_knowledge_context_without_answer(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "explanation-hint.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _start_quiz(at)
    _wrong_once(at, "y² = x")

    assert not at.exception
    text = _text(at)
    assert "知识点定位" in text
    assert "函数的概念" in text
    assert "标准答案" not in text
    assert any("先修链：无" in caption.value for caption in at.caption)


def test_diagnose_page_shows_localized_error(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "explanation-diagnose.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _start_quiz(at)
    _wrong_once(at, "y² = x")
    at.button[0].click().run()  # 再试一次
    _wrong_once(at, "x = 1")

    assert not at.exception
    text = _text(at)
    assert "错因定位" in text
    assert "建议先复习" in text
    assert any(button.label == "确认错因" for button in at.button)


def test_wrapup_shows_full_explanation(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "explanation-wrapup.sqlite3")
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
    text = _text(at)
    assert "完整解析" in text
    assert "标准答案：y = x²" in text
    assert "解题思路：" in text
