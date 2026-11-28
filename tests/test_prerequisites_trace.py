"""先修链诊断：BFS 沿先修边向上 1—2 层，识别概念缺口。"""
from mathcoach.domain.prerequisites import MistakeStat, trace_gap

PREREQ = {
    "hs-calculus-derivative-001": ["hs-calculus-limit-001"],
    "hs-calculus-limit-001": ["hs-function-intro-001"],
}


def test_no_gap_when_stats_healthy():
    """上游统计健康时不产生缺口。"""
    stats = {"hs-function-intro-001": MistakeStat(total=5, concept_wrong=0)}
    gaps = trace_gap("hs-calculus-derivative-001", PREREQ, stats, max_depth=2)
    assert gaps == []


def test_gap_detected_at_ancestor():
    """祖先概念错误触发缺口并记录链路。"""
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
    """深度一不触达两层外的缺口。"""
    stats = {"hs-function-intro-001": MistakeStat(total=4, concept_wrong=3)}
    gaps = trace_gap("hs-calculus-derivative-001", PREREQ, stats, max_depth=1)
    assert gaps == []  # 缺口在 2 层外，深度 1 追不到


def test_diamond_prerequisite_reported_once():
    """菱形先修只报告一次缺口。"""
    prerequisites = {
        "root": ["left", "right"],
        "left": ["shared"],
        "right": ["shared"],
    }
    stats = {"shared": MistakeStat(total=3, concept_wrong=2)}

    gaps = trace_gap("root", prerequisites, stats, max_depth=2)

    assert len(gaps) == 1
    assert gaps[0].chain == ("root", "left", "shared")
