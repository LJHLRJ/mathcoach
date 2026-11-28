"""会话引擎接入表示降级：只在视图层改变讲解形态。"""
from pathlib import Path

from mathcoach.content.loader import load_content
from mathcoach.domain.models import Phase
from mathcoach.domain.representation import Representation
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


class FakeRecorder:
    """记录降级事件与回填结果，便于断言。"""

    def __init__(self) -> None:
        self.events = []
        self.outcomes = []

    def record(self, event):
        self.events.append(event)
        return event.id

    def record_outcome(self, event_id, *, correct, hint_level):
        self.outcomes.append((event_id, correct, hint_level))


def _engine(recorder=None) -> SessionEngine:
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card = next(card for card in cards if card.id == "hs-function-intro-001")
    return SessionEngine(
        card=card,
        provider=OfflineProvider(),
        representation_recorder=recorder,
    )


def _first_wrong(engine: SessionEngine):
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    return engine.submit_answer("y² = x")


def test_two_signals_downgrade_hint_view():
    """连错 2 次且请求过提示后，诊断与提示视图带具体例子形态。"""
    recorder = FakeRecorder()
    engine = _engine(recorder)
    first = _first_wrong(engine)
    assert first.phase is Phase.HINT
    assert first.representation is None
    assert recorder.events == []

    engine.retry()
    engine.request_hint("step")
    engine.retry()
    view = engine.submit_answer("x = 1")

    assert view.phase is Phase.DIAGNOSE
    assert view.representation is Representation.WORKED_EXAMPLE
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert event.from_repr is Representation.FORMULA
    assert event.to_repr is Representation.WORKED_EXAMPLE
    assert any("连续错误" in reason for reason in event.triggers)

    hint = engine.confirm_diagnosis()
    assert hint.phase is Phase.HINT
    assert hint.representation is Representation.WORKED_EXAMPLE


def test_outcome_backfilled_on_next_answer():
    """降级后下一次作答会回填结果，不重复降级。"""
    recorder = FakeRecorder()
    engine = _engine(recorder)
    _first_wrong(engine)
    engine.retry()
    engine.request_hint("step")
    engine.retry()
    engine.submit_answer("x = 1")
    engine.confirm_diagnosis()
    engine.retry()

    view = engine.submit_answer("y = x²")
    assert view.phase is Phase.RECEIPT
    assert view.receipt is not None
    assert len(recorder.outcomes) == 1
    event_id, correct, hint_level = recorder.outcomes[0]
    assert event_id == recorder.events[0].id
    assert correct is True
    assert hint_level == 4


def test_representation_independent_of_hint_level():
    """降级只改讲解形态，不改变提示层级或收据。"""
    engine = _engine()
    _first_wrong(engine)
    engine.retry()
    engine.request_hint("step")
    assert engine.state.hint_level == 4
    engine.retry()
    engine.submit_answer("x = 1")
    engine.confirm_diagnosis()
    engine.retry()

    receipt = engine.submit_answer("y = x²").receipt
    assert engine.state.hint_level == 4
    assert receipt is not None
    assert receipt.max_hint_level == 4


def test_engine_without_recorder_still_downgrades():
    """没有记录器时仍可在视图层降级，不抛异常。"""
    engine = _engine()
    _first_wrong(engine)
    engine.retry()
    engine.request_hint("step")
    engine.retry()
    view = engine.submit_answer("x = 1")
    assert view.representation is Representation.WORKED_EXAMPLE
    assert engine.confirm_diagnosis().representation is (
        Representation.WORKED_EXAMPLE
    )


def test_new_exercise_resets_representation():
    """进入下一题后表示形态恢复默认，可重新决策。"""
    recorder = FakeRecorder()
    engine = _engine(recorder)
    _first_wrong(engine)
    engine.retry()
    engine.request_hint("step")
    engine.retry()
    engine.submit_answer("x = 1")
    engine.confirm_diagnosis()
    engine.retry()
    engine.submit_answer("y = x²")

    next_view = engine.advance()
    assert next_view.phase is Phase.QUIZ
    assert next_view.representation is None
    assert engine._representation is Representation.FORMULA
