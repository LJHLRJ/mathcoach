"""前置修复规划：阈值、样本量、缺失先修与低置信边。"""
from pathlib import Path

from mathcoach.config import resolve_content_root
from mathcoach.content.loader import load_content
from mathcoach.mastery import build_repair_plan
from mathcoach.tutor.kc_graph import KCEdge, KCGraph

CARDS, _ = load_content(
    resolve_content_root(Path(__file__).resolve().parents[1] / "app.py"),
    strict=False,
)
PREREQ = "kc-hs-trig-002-f1"
DEPENDENT = "kc-hs-trig-003-f1"


def _plan(**overrides):
    """生成默认的修复规划。"""
    kwargs = {
        "sample_sizes": {PREREQ: 3, DEPENDENT: 3},
    }
    kwargs.update(overrides)
    return build_repair_plan(
        CARDS,
        {PREREQ: 0.2, DEPENDENT: 0.3},
        **kwargs,
    )


def test_plan_finds_prerequisite_gap() -> None:
    """后继 KC 薄弱且先修更弱时生成修复建议。"""
    plan = _plan()

    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.dependent_kc_id == DEPENDENT
    assert item.prerequisite_kc_id == PREREQ
    assert item.prerequisite_card_id == "hs-trig-002"
    assert "补角公式" in item.reason
    assert "同角平方关系" in item.reason


def test_plan_requires_minimum_samples() -> None:
    """样本量不足时不触发。"""
    plan = _plan(sample_sizes={PREREQ: 3, DEPENDENT: 1})

    assert plan.items == ()


def test_plan_ignores_when_probabilities_high() -> None:
    """掌握度高于阈值时不触发。"""
    plan = build_repair_plan(
        CARDS,
        {PREREQ: 0.9, DEPENDENT: 0.9},
        sample_sizes={PREREQ: 3, DEPENDENT: 3},
    )

    assert plan.items == ()


def test_plan_notes_missing_prerequisite_data() -> None:
    """先修没有观测时只提示数据缺口，不生成建议。"""
    plan = build_repair_plan(
        CARDS,
        {DEPENDENT: 0.2},
        sample_sizes={DEPENDENT: 3},
    )

    assert plan.items == ()
    assert any("先修缺少观测" in note for note in plan.notes)


def test_low_confidence_edge_is_ignored() -> None:
    """置信度低于阈值的边不触发修复。"""
    edge = KCEdge(
        from_kc=PREREQ,
        to_kc=DEPENDENT,
        confidence=0.5,
    )
    graph = KCGraph({DEPENDENT: (edge,)})

    plan = _plan(graph=graph)

    assert plan.items == ()
