"""叙事线：首节点、收据推进、禁止跳级、关闭状态与无时钟纯函数。"""
from dataclasses import replace
from pathlib import Path

import yaml

from mathcoach.domain.narrative import (
    NarrativeNode,
    NarrativeProgress,
    advance,
    first_node,
    initial_progress,
    narrative_closed,
)

ROOT = Path(__file__).resolve().parents[1]

NODES = [
    NarrativeNode("n1", "c1", "起点", "从集合出发"),
    NarrativeNode("n2", "c2", "函数之门", "看见变化"),
    NarrativeNode("n3", "c3", "极限之光", "逼近真相"),
]


def test_first_node():
    assert first_node(NODES) == NODES[0]
    assert initial_progress(NODES).unlocked == ("n1",)


def test_advance_on_receipt():
    progress = initial_progress(NODES)

    progress = advance(progress, NODES, "c2")

    assert progress.unlocked == ("n1", "n2")


def test_no_skip():
    progress = initial_progress(NODES)

    unchanged = advance(progress, NODES, "c3")

    assert unchanged == progress


def test_narrative_closed():
    progress = NarrativeProgress(unlocked=("n1", "n2", "n3"))

    assert narrative_closed(progress, NODES)
    assert not narrative_closed(initial_progress(NODES), NODES)


def test_narrative_disabled_does_not_advance():
    progress = initial_progress(NODES)

    unchanged = advance(progress, NODES, "c2", enabled=False)

    assert unchanged == progress


def test_pure_no_clock_and_deterministic():
    import mathcoach.domain.narrative as narrative

    assert not hasattr(narrative, "datetime")
    assert not hasattr(narrative, "time")

    progress = initial_progress(NODES)
    first = advance(progress, NODES, "c2")
    second = advance(progress, NODES, "c2")

    assert first == second
    assert progress == replace(initial_progress(NODES))


def test_narrative_file_has_20_to_30_nodes():
    data = yaml.safe_load(
        (ROOT / "content/narrative.yaml").read_text(encoding="utf-8")
    )

    nodes = data["nodes"]
    assert 20 <= len(nodes) <= 30
    assert all(
        {"id", "card_id", "name", "description"} <= set(node) for node in nodes
    )


def test_load_narrative_returns_nodes():
    from mathcoach.content.loader import load_narrative

    nodes = load_narrative(ROOT / "content")

    assert len(nodes) == 24
    assert nodes[0].id == "n01"
    assert nodes[0].card_id == "hs-set-001"
