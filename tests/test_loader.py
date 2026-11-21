"""加载器把 YAML 转成 dataclass，并在校验失败时中止。"""
import copy
from pathlib import Path

import pytest
import yaml

from mathcoach.content.loader import ContentError, load_content
from mathcoach.domain.models import ExerciseKind, Stage

CURRICULUM = [
    {
        "stage": "highschool",
        "course": "函数与导数",
        "module": "函数与导数",
        "chapter": "函数概念",
        "card_ids": ["hs-001"],
    }
]

CARD = {
    "id": "hs-001",
    "name": "函数的概念",
    "stage": "highschool",
    "course": "函数与导数",
    "chapter": "函数概念",
    "difficulty": "基础",
    "intuition": "输入唯一输出",
    "definition": "每个 x 对应唯一 y",
    "mistakes": ["忽略定义域"],
    "example": "y = x²",
    "source": "智能体生成",
    "exercises": [
        {
            "id": "hs-001-e1",
            "kind": "choice",
            "stem": "题干",
            "options": ["A", "B"],
            "answer": "A",
            "solution_outline": "因为 A",
        }
    ],
}


def _write_tree(root: Path, curriculum=CURRICULUM, cards=None):
    cards = cards if cards is not None else [CARD]
    (root / "curriculum.yaml").write_text(
        yaml.safe_dump(curriculum, allow_unicode=True), encoding="utf-8"
    )
    folder = root / "highschool"
    folder.mkdir(exist_ok=True)
    for index, card in enumerate(cards):
        (folder / f"card-{index}.yaml").write_text(
            yaml.safe_dump(card, allow_unicode=True), encoding="utf-8"
        )


def test_load_content_returns_dataclasses(tmp_path):
    _write_tree(tmp_path)
    cards, result = load_content(tmp_path, strict=True)

    assert result.ok
    assert len(cards) == 1
    card = cards[0]
    assert card.id == "hs-001"
    assert card.stage is Stage.HIGH_SCHOOL
    assert card.exercises[0].kind is ExerciseKind.CHOICE
    assert card.exercises[0].card_id == "hs-001"
    assert card.exercises[0].options == ("A", "B")


def test_load_content_raises_on_strict_issue(tmp_path):
    curriculum = [dict(CURRICULUM[0], card_ids=["hs-001", "hs-999"])]
    _write_tree(tmp_path, curriculum=curriculum)

    with pytest.raises(ContentError) as excinfo:
        load_content(tmp_path, strict=True)
    assert "未完成条目" in str(excinfo.value)


def test_load_content_allows_warning_in_non_strict_mode(tmp_path):
    curriculum = [dict(CURRICULUM[0], card_ids=["hs-001", "hs-999"])]
    _write_tree(tmp_path, curriculum=curriculum)

    cards, result = load_content(tmp_path, strict=False)
    assert len(cards) == 1
    assert result.ok
    assert len(result.warnings) == 1


def test_multi_answer_is_canonicalized(tmp_path):
    card = copy.deepcopy(CARD)
    card["exercises"][0] = {
        "id": "hs-001-e1",
        "kind": "multi",
        "stem": "题干",
        "options": ["A", "B"],
        "answer": ["A", "B"],
        "solution_outline": "因为 A、B",
    }
    _write_tree(tmp_path, cards=[card])

    cards, _ = load_content(tmp_path, strict=True)
    assert cards[0].exercises[0].answer == "A,B"


def test_top_level_config_yaml_is_not_treated_as_card(tmp_path):
    _write_tree(tmp_path)
    # 顶层参数文件不是知识卡片，不能被 load_raw_cards 收集
    (tmp_path / "fsrs_params.yaml").write_text(
        "desired_retention: 0.9\n", encoding="utf-8"
    )

    cards, result = load_content(tmp_path, strict=True)

    assert result.ok
    assert len(cards) == 1

