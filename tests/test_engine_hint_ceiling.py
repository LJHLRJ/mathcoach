"""依赖度防护：提示上限、恢复与默认行为不回归。"""
from pathlib import Path

from mathcoach.content.loader import load_content
from mathcoach.domain.models import Phase
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def _engine(hint_ceiling: int | None = None) -> SessionEngine:
    """构造入门卡的引擎并推进到小测。"""
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card = next(
        card for card in cards if card.id == "hs-function-intro-001"
    )
    engine = SessionEngine(
        card=card,
        provider=OfflineProvider(),
        hint_ceiling=hint_ceiling,
    )
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    return engine


def test_default_engine_keeps_full_hint_ladder() -> None:
    """默认不启用上限时，请求步骤仍到 L4。"""
    engine = _engine()

    view = engine.request_hint("step")

    assert engine.hint_ceiling_active is False
    assert engine.state.hint_level == 4
    assert view.title == "提示 L4"


def test_explicit_step_request_is_capped_to_l2() -> None:
    """启用上限后，主动请求步骤只到 L2。"""
    engine = _engine(hint_ceiling=2)

    view = engine.request_hint("step")

    assert engine.hint_ceiling_active is True
    assert engine.state.hint_level == 2
    assert view.title == "提示 L2"
    assert "先自己试" in view.body
    assert engine.state.max_hint_level == 2


def test_explicit_answer_request_is_capped() -> None:
    """主动请求答案同样只到 L2。"""
    engine = _engine(hint_ceiling=2)

    view = engine.request_hint("answer")

    assert engine.state.hint_level == 2
    assert "先自己试" in view.body


def test_level5_request_does_not_raise_level() -> None:
    """上限期间 L5 请求不提升层级。"""
    engine = _engine(hint_ceiling=2)

    view = engine.request_hint("level5")

    assert engine.state.hint_level == 1
    assert "暂不开放 L5" in view.body
    assert engine.hint_ceiling_active is True


def test_two_wrong_answers_release_ceiling() -> None:
    """连续两次答错自动恢复完整提示。"""
    engine = _engine(hint_ceiling=2)

    engine.submit_answer("x = 1")
    engine.retry()
    view = engine.submit_answer("y² = x")

    assert view.phase is Phase.DIAGNOSE
    assert engine.hint_ceiling_active is False
    assert "已恢复完整提示" in view.body


def test_independent_correct_releases_ceiling() -> None:
    """独立答对后解除上限。"""
    engine = _engine(hint_ceiling=2)

    view = engine.submit_answer("y = x²")

    assert view.phase is Phase.RECEIPT
    assert engine.hint_ceiling_active is False


def test_manual_release_restores_full_ladder() -> None:
    """手动恢复后再次请求步骤可到 L4。"""
    engine = _engine(hint_ceiling=2)

    assert engine.release_hint_ceiling("manual") is True
    assert engine.release_hint_ceiling("manual") is False

    view = engine.request_hint("step")

    assert engine.state.hint_level == 4
    assert view.title == "提示 L4"


def test_advance_releases_remaining_ceiling() -> None:
    """收据未解除时，进入下一题会解除上限。"""
    engine = _engine(hint_ceiling=2)
    engine.state.max_hint_level = 4

    view = engine.submit_answer("y = x²")

    assert view.phase is Phase.RECEIPT
    assert engine.hint_ceiling_active is True

    engine.advance()

    assert engine.hint_ceiling_active is False
