"""先修缺口在 BFS 生成时写入依据，并可在文字视图展示。"""
from mathcoach.domain.prerequisites import MistakeStat, trace_gap
from mathcoach.session.diagnosis_view import render_gaps

PREREQUISITES = {
    "child": ["parent-a", "parent-b"],
    "parent-a": ["grandparent"],
}


def test_trace_gap_adds_basis_to_every_gap():
    stats = {
        "parent-a": MistakeStat(total=3, concept_wrong=2),
        "parent-b": MistakeStat(total=4, concept_wrong=3),
    }

    gaps = trace_gap("child", PREREQUISITES, stats, max_depth=1)

    assert len(gaps) == 2
    assert all(gap.basis for gap in gaps)
    assert "2/3" in gaps[0].basis
    assert "3/4" in gaps[1].basis


def test_gap_basis_multiple_parents_renders_each_basis():
    stats = {
        "parent-a": MistakeStat(total=2, concept_wrong=2),
        "parent-b": MistakeStat(total=4, concept_wrong=3),
    }

    gaps = trace_gap("child", PREREQUISITES, stats, max_depth=1)
    text = render_gaps(gaps)

    assert text.count("依据：") == 2
    assert "2/2" in text
    assert "3/4" in text
