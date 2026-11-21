"""知识点树结构：规模、父子查询、先修链与非法结构拒绝。"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mathcoach.domain.knowledge_tree import (
    KnowledgeTreeError,
    load_knowledge_tree,
)

ROOT = Path(__file__).resolve().parents[1]
TREE_PATH = ROOT / "content" / "knowledge_tree.yaml"


def test_tree_loads_with_expected_scale():
    tree = load_knowledge_tree(TREE_PATH)

    assert len(tree.nodes) == 148
    assert len(tree.bindings) == 366
    assert tree.node("stage-highschool").name == "高中"
    assert tree.node("hs-function-intro-001").name == "函数的概念"


def test_children_follow_stage_course_card_hierarchy():
    tree = load_knowledge_tree(TREE_PATH)

    stage_children = tree.children("stage-highschool")
    assert any(
        node.id == "course-hs-函数与导数" for node in stage_children
    )
    course_children = tree.children("course-hs-函数与导数")
    assert any(
        node.id == "hs-function-intro-001" for node in course_children
    )
    assert tree.children("hs-function-intro-001") == ()


def test_prerequisite_chain_is_bounded_and_deterministic():
    tree = load_knowledge_tree(TREE_PATH)

    assert tree.prerequisite_chain("hs-func-003") == (
        "hs-func-002",
        "hs-function-intro-001",
    )
    assert tree.prerequisite_chain("hs-func-003", max_depth=1) == (
        "hs-func-002",
    )
    assert tree.prerequisite_chain("hs-func-003", max_depth=0) == ()
    assert tree.prerequisite_chain("unknown-node") == ()


def _write_tree(path: Path, nodes: list[dict], bindings=None) -> Path:
    path.write_text(
        yaml.safe_dump(
            {"nodes": nodes, "bindings": bindings or []},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _node(node_id: str, prerequisites: list[str] | None = None) -> dict:
    return {
        "id": node_id,
        "name": node_id,
        "parent_id": None,
        "prerequisites": prerequisites or [],
        "description": f"节点 {node_id}",
    }


def test_missing_prerequisite_is_rejected(tmp_path):
    path = _write_tree(
        tmp_path / "missing.yaml",
        [_node("a", ["missing"])],
    )

    with pytest.raises(KnowledgeTreeError, match="先修节点不存在"):
        load_knowledge_tree(path)


def test_cycle_is_rejected(tmp_path):
    path = _write_tree(
        tmp_path / "cycle.yaml",
        [_node("a", ["b"]), _node("b", ["a"])],
    )

    with pytest.raises(KnowledgeTreeError, match="存在环"):
        load_knowledge_tree(path)


def test_duplicate_node_id_is_rejected(tmp_path):
    path = _write_tree(
        tmp_path / "duplicate.yaml",
        [_node("a"), _node("a")],
    )

    with pytest.raises(KnowledgeTreeError, match="知识点 ID 重复"):
        load_knowledge_tree(path)
