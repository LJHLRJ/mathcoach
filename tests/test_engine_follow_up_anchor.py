"""追问锚点：从当前步骤发起的追问保持步骤上下文。"""
from pathlib import Path

from mathcoach.content.loader import load_content
from mathcoach.domain.models import Phase
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.session.engine import SessionEngine
from mathcoach.tutor.dialog import (
    CATALOG,
    FollowUp,
    FollowUpBuild,
)

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def _engine() -> SessionEngine:
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card = next(card for card in cards if card.id == "hs-trig-002")
    return SessionEngine(card=card, provider=OfflineProvider())


def _build():
    """构造带指定层级元数据的追问；问法固定，不调用 LLM。"""

    def fake_build(exercise_id, level, **kwargs):
        spec = CATALOG.specs[(exercise_id, level)]
        return FollowUpBuild(
            FollowUp(spec=spec, prompt=f"L{level} 追问"),
            spec,
        )

    return fake_build


def test_request_hint_carries_step_anchor(monkeypatch) -> None:
    """从步骤区请求提示时，追问视图带当前步骤序号。"""
    engine = _engine()
    engine.confirm_goal("搞懂同角平方关系")
    engine.begin_quiz()
    monkeypatch.setattr(
        "mathcoach.session.engine.build_follow_up", _build()
    )

    engine.request_hint("step", step_index=1)

    assert engine.view.follow_up is not None
    assert engine.view.follow_up.anchor_step_index == 1


def test_follow_up_chain_keeps_anchor(monkeypatch) -> None:
    """L3 命中进入 L4 时仍锚定同一步骤。"""
    engine = _engine()
    engine.confirm_goal("搞懂同角平方关系")
    engine.begin_quiz()
    monkeypatch.setattr(
        "mathcoach.session.engine.build_follow_up", _build()
    )
    engine._start_follow_up(3, anchor_step_index=1)
    assert engine._active_follow_up is not None
    engine.state.phase = Phase.HINT
    engine._render_follow_up(engine._active_follow_up, "")
    assert engine.view.follow_up.anchor_step_index == 1

    monkeypatch.setattr(
        "mathcoach.session.engine.build_follow_up", _build()
    )
    view = engine.submit_follow_up("1")

    assert view.follow_up is not None
    assert view.follow_up.level == 4
    assert view.follow_up.anchor_step_index == 1
