"""先修链诊断：BFS 沿先修边向上 1—2 层，识别概念缺口。"""
from datetime import datetime, timezone

from mathcoach.domain.prerequisites import Gap, MistakeStat, trace_gap

NOW = datetime(2026, 11, 21, tzinfo=timezone.utc)

PREREQ = {
    "hs-calculus-derivative-001": ["hs-calculus-limit-001"],
    "hs-calculus-limit-001": ["hs-function-intro-001"],
}


def test_no_gap_when_stats_healthy():
    stats = {"hs-function-intro-001": MistakeStat(total=5, concept_wrong=0)}
    gaps = trace_gap("hs-calculus-derivative-001", PREREQ, stats, max_depth=2)
    assert gaps == []


def test_gap_detected_at_ancestor():
    stats = {"hs-function-intro-001": MistakeStat(total=4, concept_wrong=3)}
    gaps = trace_gap("hs-calculus-derivative-001", PREREQ, stats, max_depth=2)
    assert len(gaps) == 1
    assert gaps[0].chain == (
        "hs-calculus-derivative-001",
        "hs-calculus-limit-001",
        "hs-function-intro-001",
    )
    assert "概念" in gaps[0].reason


def test_max_depth_limits_traversal():
    stats = {"hs-function-intro-001": MistakeStat(total=4, concept_wrong=3)}
    gaps = trace_gap("hs-calculus-derivative-001", PREREQ, stats, max_depth=1)
    assert gaps == []  # 缺口在 2 层外，深度 1 追不到
