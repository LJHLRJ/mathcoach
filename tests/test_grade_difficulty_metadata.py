"""年级/难度元数据：枚举、全量覆盖、查询过滤与 grade_span。"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from mathcoach.content.loader import load_content
from mathcoach.domain.grade_index import (
    DIFFICULTY_VALUES,
    GRADE_VALUES,
    UNCLASSIFIED,
    GradeIndexError,
    build_grade_index,
    load_grade_index,
    load_grade_spans,
    node_ids_for_grade,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content"
TREE_PATH = CONTENT_ROOT / "knowledge_tree.yaml"


def _loaded_cards():
    cards, result = load_content(CONTENT_ROOT, strict=True)
    assert result.ok
    return cards


def test_grade_and_difficulty_enums_cover_required_values():
    assert GRADE_VALUES == (
        "g1",
        "g2",
        "g3",
        "g4",
        "g5",
        "g6",
        "g7",
        "g8",
        "g9",
        "g10",
        "g11",
        "g12",
        "u1",
        "u2",
        "u3",
        "u4",
        "m1",
        "m2",
        "m3",
        "mixed",
    )
    assert DIFFICULTY_VALUES == (
        "basic",
        "intermediate",
        "advanced",
        "challenge",
    )
    assert UNCLASSIFIED not in GRADE_VALUES
    assert UNCLASSIFIED not in DIFFICULTY_VALUES


def test_every_loaded_exercise_has_metadata():
    cards = _loaded_cards()
    index = load_grade_index(CONTENT_ROOT)
    loaded_ids = {
        exercise.id for card in cards for exercise in card.exercises
    }

    assert len(loaded_ids) == 366
    assert set(index.records) == loaded_ids
    assert {record.grade for record in index.records.values()} == {
        "mixed"
    }
    assert index.difficulty_counts() == {
        "basic": 138,
        "intermediate": 141,
        "advanced": 0,
        "challenge": 87,
        "unclassified": 0,
    }
    assert index.grade_counts()["mixed"] == 366


def test_index_filters_by_grade_and_difficulty():
    index = load_grade_index(CONTENT_ROOT)

    assert len(index.by_grade("mixed")) == 366
    assert index.by_grade("g1") == ()
    assert len(index.by_difficulty("basic")) == 138
    assert len(index.filter("mixed", "challenge")) == 87
    assert index.filter("g1") == ()

    card_ids = index.card_ids("mixed")
    assert len(card_ids) == 122
    assert len(set(card_ids)) == 122


def test_missing_metadata_falls_back_to_unclassified():
    index = build_grade_index(
        [{"id": "demo-card", "exercises": [{"id": "demo-card-e1"}]}]
    )

    record = index.records["demo-card-e1"]
    assert record.grade == UNCLASSIFIED
    assert record.difficulty == UNCLASSIFIED
    assert index.by_grade(UNCLASSIFIED) == (record,)
    assert index.by_difficulty(UNCLASSIFIED) == (record,)


def test_duplicate_exercise_ids_are_rejected():
    with pytest.raises(GradeIndexError, match="题目 ID 重复"):
        build_grade_index(
            [
                {
                    "id": "demo-card",
                    "exercises": [
                        {"id": "demo-card-e1"},
                        {"id": "demo-card-e1"},
                    ],
                }
            ]
        )


def test_grade_spans_cover_every_tree_node():
    spans = load_grade_spans(TREE_PATH)

    assert len(spans) == 148
    assert set(spans.values()) == {("mixed",)}
    assert len(node_ids_for_grade(spans, "mixed")) == 148
    assert node_ids_for_grade(spans, "g1") == ()


def test_existing_card_fields_are_preserved():
    cards = _loaded_cards()

    assert len(cards) == 122
    assert sum(len(card.exercises) for card in cards) == 366
    assert Counter(card.difficulty.value for card in cards) == {
        "基础": 46,
        "进阶": 47,
        "挑战": 29,
    }
    for card in cards:
        for exercise in card.exercises:
            assert exercise.stem
            assert exercise.answer
            assert exercise.solution_outline
