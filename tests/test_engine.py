"""状态机全部转移路径必须可测，app 不得参与判定。"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mathcoach.content.loader import load_content
from mathcoach.domain.models import (
    Difficulty,
    ErrorType,
    Exercise,
    ExerciseKind,
    Independence,
    KnowledgeCard,
    Phase,
    Stage,
)
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture()
def engine() -> SessionEngine:
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card = next(card for card in cards if card.id == "hs-function-intro-001")
    return SessionEngine(card=card, provider=OfflineProvider())


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
    view = engine.submit_answer("x = 1")
    assert view.phase is Phase.DIAGNOSE
    engine.confirm_diagnosis()
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


def test_advance_resets_max_hint_level(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()

    # 第 1 题：先答错两次，确认错因后再请求“给步骤”升到 L4
    engine.submit_answer("y² = x")
    engine.retry()
    engine.submit_answer("x = 1")
    engine.confirm_diagnosis()
    engine.request_hint("step")
    engine.retry()
    view = engine.submit_answer("y = x²")
    assert view.receipt.max_hint_level == 4

    engine.advance()  # 进入第 2 题，必须把 max_hint_level 归零
    view = engine.submit_answer("x ≥ 2")  # 第 2 题在 L1 独立答对
    assert view.receipt.independence is Independence.INDEPENDENT
    assert view.receipt.max_hint_level == 1


def test_wrong_answer_does_not_inflate_max_hint_level(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")  # 在 L1 作答答错
    assert engine.state.max_hint_level == 1  # 不是升到 L2 后的 2


def test_hint_level_3_uses_card_intuition(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")  # L1 → L2
    engine.retry()
    view = engine.submit_answer("x = 1")  # 连错 2 次 → 诊断
    assert view.phase is Phase.DIAGNOSE
    assert engine.state.diagnosis is not None

    view = engine.confirm_diagnosis()
    assert engine.state.hint_level == 3
    assert engine.card.intuition in view.body


def test_receipt_duration_measures_single_exercise(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    # 模拟本题已用时 5 秒；收据应按单题计时而非整个会话
    engine.state.exercise_started_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    view = engine.submit_answer("y = x²")
    assert view.receipt.duration_s >= 5


def test_second_wrong_answer_triggers_diagnosis(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    engine.retry()

    view = engine.submit_answer("x = 1")
    assert view.phase is Phase.DIAGNOSE
    assert view.options == tuple(item.value for item in ErrorType)
    assert "不改变判分" in view.notice


def test_automatic_hint_never_opens_l5(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.request_hint("step")  # 显式请求到 L4
    engine.retry()
    view = engine.submit_answer("y² = x")
    assert view.phase is Phase.HINT
    assert engine.state.hint_level == 4  # 答错不自动进 L5


def test_diagnosis_can_be_overridden(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    engine.retry()
    engine.submit_answer("x = 1")

    engine.confirm_diagnosis("计算失误")
    assert engine.state.diagnosis is ErrorType.CALCULATION
    assert engine.state.phase is Phase.HINT


def test_confirm_diagnosis_is_phase_guarded(engine):
    with pytest.raises(RuntimeError):
        engine.confirm_diagnosis()
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    with pytest.raises(RuntimeError):
        engine.confirm_diagnosis("计算失误")


def test_unknown_diagnosis_label_raises(engine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    engine.retry()
    engine.submit_answer("x = 1")
    with pytest.raises(ValueError):
        engine.confirm_diagnosis("不存在的错因")


def test_unverified_expr_does_not_count_as_wrong():
    exercise = Exercise(
        id="hs-test-e1",
        card_id="hs-test",
        kind=ExerciseKind.EXPR,
        stem="展开 (x+1)²",
        answer="x**2 + 2*x + 1",
        solution_outline="完全平方公式",
    )
    card = KnowledgeCard(
        id="hs-test",
        name="测试卡片",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        chapter="测试",
        difficulty=Difficulty.BASIC,
        intuition="展开",
        definition="展开",
        mistakes=(),
        example="(x+1)²",
        exercises=(exercise,),
        source="智能体生成",
    )
    engine = SessionEngine(card=card, provider=OfflineProvider())
    engine.confirm_goal("练展开")
    engine.begin_quiz()

    view = engine.submit_answer("__import__('os')")
    assert view.phase is Phase.QUIZ
    assert engine.state.consecutive_wrong == 0
    assert "人工核对" in view.notice

    view = engine.submit_answer("(x + 1)**2")
    assert view.phase is Phase.RECEIPT
