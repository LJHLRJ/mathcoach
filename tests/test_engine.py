"""状态机全部转移路径必须可测，app 不得参与判定。"""
from pathlib import Path

import pytest

from mathcoach.content.loader import load_content
from mathcoach.domain.models import Independence, Phase
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture()
def engine() -> SessionEngine:
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    return SessionEngine(card=cards[0], provider=OfflineProvider())


def test_happy_path_issues_receipt(engine):
    assert engine.view.phase is Phase.GOAL_CONFIRM

    view = engine.confirm_goal("搞懂函数的概念")
    assert view.phase is Phase.EXPLAIN
    assert "定义" in view.body

    view = engine.begin_quiz()
    assert view.phase is Phase.QUIZ
    assert view.options == ("y = x²", "x² + y² = 1", "y² = x", "x = 1")

    view = engine.submit_answer("y = x²")
    assert view.phase is Phase.RECEIPT
    assert view.receipt is not None
    assert view.receipt.independence is Independence.INDEPENDENT
    assert len(engine.receipts) == 1


def test_wrong_answer_escalates_hint(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()

    view = engine.submit_answer("y² = x")
    assert view.phase is Phase.HINT
    assert engine.state.hint_level == 2

    view = engine.retry()
    assert view.phase is Phase.QUIZ


def test_three_wrong_answers_end_without_receipt(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()

    engine.submit_answer("y² = x")
    engine.retry()
    engine.submit_answer("x = 1")
    engine.retry()
    view = engine.submit_answer("x² + y² = 1")

    assert view.phase is Phase.WRAPUP
    assert engine.receipts == []


def test_request_step_marks_semi_independent(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()

    view = engine.request_hint("step")
    assert view.phase is Phase.HINT
    assert engine.state.hint_level == 4

    engine.retry()
    view = engine.submit_answer("y = x²")
    assert view.phase is Phase.RECEIPT
    assert view.receipt.independence is Independence.SEMI_INDEPENDENT
    assert view.receipt.max_hint_level == 4


def test_advance_moves_to_next_exercise_then_wrapup(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y = x²")
    view = engine.advance()
    assert view.phase is Phase.QUIZ
    assert "第 2 / 3 题" in view.title

    engine.submit_answer("x ≥ 2")
    engine.advance()
    engine.submit_answer("7")
    view = engine.advance()
    assert view.phase is Phase.WRAPUP
    assert len(engine.receipts) == 3


def test_actions_are_phase_guarded(engine):
    with pytest.raises(RuntimeError):
        engine.begin_quiz()
    with pytest.raises(ValueError):
        engine.confirm_goal("   ")
