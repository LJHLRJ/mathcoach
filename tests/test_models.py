"""枚举值必须与 YAML 内容中的字面量一致。"""
import dataclasses

import pytest

from mathcoach.domain.models import (
    Difficulty,
    Exercise,
    ExerciseKind,
    Independence,
    KnowledgeCard,
    Stage,
)


def test_enum_values_match_content_literals():
    assert Stage.HIGH_SCHOOL.value == "highschool"
    assert Difficulty.BASIC.value == "基础"
    assert ExerciseKind.CHOICE.value == "choice"
    assert Independence.SEMI_INDEPENDENT.value == "半独立完成"


def test_card_and_exercise_are_frozen():
    exercise = Exercise(
        id="hs-001-e1",
        card_id="hs-001",
        kind=ExerciseKind.CHOICE,
        stem="题干",
        answer="A",
        solution_outline="因为 A",
        options=("A", "B"),
    )
    card = KnowledgeCard(
        id="hs-001",
        name="函数的概念",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        chapter="函数概念",
        difficulty=Difficulty.BASIC,
        intuition="输入唯一输出",
        definition="每个 x 对应唯一 y",
        mistakes=("忽略定义域",),
        example="y = x²",
        exercises=(exercise,),
        source="智能体生成",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        card.name = "改不了"
