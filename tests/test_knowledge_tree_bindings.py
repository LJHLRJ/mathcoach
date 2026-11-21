"""知识点与题目绑定：全量覆盖、schema 格式与 unmapped 查询。"""
from __future__ import annotations

from pathlib import Path

import yaml

from mathcoach.content.loader import load_content
from mathcoach.domain.knowledge_tree import (
    UNMAPPED,
    load_knowledge_tree,
)

ROOT = Path(__file__).resolve().parents[1]
TREE_PATH = ROOT / "content" / "knowledge_tree.yaml"


def test_every_card_and_exercise_is_bound():
    cards, result = load_content(ROOT / "content", strict=False)
    tree = load_knowledge_tree(TREE_PATH)

    assert result.ok
    bound = 0
    for card in cards:
        assert tree.node(card.id) is not None
        for exercise in card.exercises:
            binding = tree.problem_for(exercise.id)
            assert binding is not None
            assert binding.knowledge_point_id == card.id
            assert binding.problem_schema == (
                f"{card.id}:{exercise.kind.value}"
            )
            bound += 1
    assert bound == 366
    assert len(tree.bindings) == 366
    assert tree.unmapped_problems() == ()


def test_problems_are_queryable_by_knowledge_point():
    tree = load_knowledge_tree(TREE_PATH)

    bindings = tree.problems_for("hs-function-intro-001")
    assert len(bindings) == 3
    assert {binding.exercise_id for binding in bindings} == {
        "hs-function-intro-001-e1",
        "hs-function-intro-001-e2",
        "hs-function-intro-001-e3",
    }
    assert all(
        binding.knowledge_point_id == "hs-function-intro-001"
        for binding in bindings
    )
    assert tree.problems_for("course-hs-函数与导数") == ()


def test_unmapped_marker_is_queryable(tmp_path):
    path = tmp_path / "unmapped.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "nodes": [
                    {
                        "id": "kp-a",
                        "name": "知识点 A",
                        "parent_id": None,
                        "prerequisites": [],
                        "description": "示例节点",
                    }
                ],
                "bindings": [
                    {
                        "exercise_id": "ex-1",
                        "knowledge_point_id": UNMAPPED,
                        "problem_schema": "unknown_schema",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    tree = load_knowledge_tree(path)
    assert [binding.exercise_id for binding in tree.unmapped_problems()] == [
        "ex-1"
    ]
