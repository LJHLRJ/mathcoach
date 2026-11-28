"""学习路径：拓扑排序、只推荐未掌握、错题优先、恰好 3 条、环检测。"""
import pytest

from mathcoach.domain.learning_path import (
    Recommendation,
    recommend,
    topological_order,
)


def test_topological_order_respects_prerequisites():
    """拓扑排序满足先修顺序。"""
    order = topological_order(
        ["c", "b", "a"],
        {"c": ["b"], "b": ["a"]},
    )

    assert order.index("a") < order.index("b") < order.index("c")


def test_recommend_only_unmastered():
    """只推荐未掌握卡片。"""
    recommendations = recommend(
        ["a", "b", "c"],
        {},
        mastered={"a"},
        weak_cards=set(),
        limit=3,
    )

    assert [item.card_id for item in recommendations] == ["b", "c"]


def test_recommend_prioritizes_weak_points():
    """错题卡优先并给出理由。"""
    recommendations = recommend(
        ["a", "b", "c"],
        {},
        mastered=set(),
        weak_cards={"b"},
        limit=3,
    )

    assert recommendations[0].card_id == "b"
    assert "错题" in recommendations[0].reason


def test_recommend_returns_three():
    """默认恰好返回三条且带理由与依据。"""
    recommendations = recommend(
        ["a", "b", "c", "d", "e"],
        {},
        mastered=set(),
        weak_cards=set(),
        limit=3,
    )

    assert len(recommendations) == 3
    assert all(isinstance(item, Recommendation) for item in recommendations)
    assert all(item.reason and item.basis for item in recommendations)


def test_cycle_raises():
    """先修成环抛出 ValueError。"""
    with pytest.raises(ValueError):
        topological_order(["a", "b"], {"a": ["b"], "b": ["a"]})


def test_recommend_marks_unmet_prerequisites_when_padding():
    """补齐时标注先修是否满足。"""
    recommendations = recommend(
        ["a", "b"],
        {"b": ["a"]},
        mastered=set(),
        weak_cards=set(),
        limit=2,
    )

    by_id = {item.card_id: item for item in recommendations}
    assert "先修已满足" in by_id["a"].reason
    assert "先修尚未满足" in by_id["b"].reason
    assert "待掌握 1 张" in by_id["b"].basis


def test_recommend_orders_ready_cards_by_mastery():
    """就绪卡按掌握度升序排列。"""
    recommendations = recommend(
        ["a", "b", "c"],
        {},
        mastered=set(),
        weak_cards=set(),
        limit=3,
        mastery={"a": 0.8, "b": 0.4, "c": 0.2},
    )

    assert [item.card_id for item in recommendations] == ["c", "b", "a"]
    assert "掌握度" in recommendations[0].reason
    assert "20%" in recommendations[0].basis


def test_recommend_keeps_weak_cards_first_over_low_mastery():
    """错题卡优先于低掌握度卡。"""
    recommendations = recommend(
        ["a", "b"],
        {},
        mastered=set(),
        weak_cards={"a"},
        limit=2,
        mastery={"a": 0.9, "b": 0.2},
    )

    assert recommendations[0].card_id == "a"
    assert "错题" in recommendations[0].reason


def test_recommend_treats_missing_mastery_as_initial():
    """缺少掌握度记录按初始值处理。"""
    recommendations = recommend(
        ["a", "b"],
        {},
        mastered=set(),
        weak_cards=set(),
        limit=2,
        mastery={"b": 0.1},
    )

    assert [item.card_id for item in recommendations] == ["b", "a"]
    assert "BKT 暂无记录" in recommendations[1].basis
