"""学习路径：拓扑排序、只推荐未掌握、错题优先、恰好 3 条、环检测。"""
import pytest

from mathcoach.domain.learning_path import (
    Recommendation,
    recommend,
    topological_order,
)


def test_topological_order_respects_prerequisites():
    order = topological_order(
        ["c", "b", "a"],
        {"c": ["b"], "b": ["a"]},
    )

    assert order.index("a") < order.index("b") < order.index("c")


def test_recommend_only_unmastered():
    recommendations = recommend(
        ["a", "b", "c"],
        {},
        mastered={"a"},
        weak_cards=set(),
        limit=3,
    )

    assert [item.card_id for item in recommendations] == ["b", "c"]


def test_recommend_prioritizes_weak_points():
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
    with pytest.raises(ValueError):
        topological_order(["a", "b"], {"a": ["b"], "b": ["a"]})
