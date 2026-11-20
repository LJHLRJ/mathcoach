"""校验器必须覆盖设计文档 §4.4 的每一条。"""
import copy

from mathcoach.content.validator import validate

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


def _card():
    return copy.deepcopy(CARD)


def test_happy_path_ok():
    result = validate(copy.deepcopy(CURRICULUM), [_card()], strict=True)
    assert result.ok
    assert result.issues == []


def test_duplicate_card_id():
    cards = [_card(), _card()]
    result = validate(copy.deepcopy(CURRICULUM), cards, strict=True)
    assert not result.ok
    assert any("id 重复" in issue.message for issue in result.issues)


def test_course_must_exist_in_curriculum():
    card = _card()
    card["course"] = "不存在的课"
    result = validate(copy.deepcopy(CURRICULUM), [card], strict=True)
    assert not result.ok
    assert any("不在 curriculum.yaml" in issue.message for issue in result.issues)


def test_source_must_be_three_choice_enum():
    card = _card()
    card["source"] = "网上下载"
    result = validate(copy.deepcopy(CURRICULUM), [card], strict=True)
    assert not result.ok
    assert any("source" in issue.message for issue in result.issues)


def test_exercise_requires_solution_outline():
    card = _card()
    del card["exercises"][0]["solution_outline"]
    result = validate(copy.deepcopy(CURRICULUM), [card], strict=True)
    assert not result.ok
    assert any("solution_outline" in issue.message for issue in result.issues)


def test_exercise_id_must_use_card_prefix():
    card = _card()
    card["exercises"][0]["id"] = "wrong-e1"
    result = validate(copy.deepcopy(CURRICULUM), [card], strict=True)
    assert not result.ok
    assert any("前缀" in issue.message for issue in result.issues)


def test_unfinished_entry_is_error_in_strict_mode():
    curriculum = copy.deepcopy(CURRICULUM)
    curriculum[0]["card_ids"].append("hs-999")
    result = validate(curriculum, [_card()], strict=True)
    assert not result.ok
    assert any("未完成条目" in issue.message for issue in result.issues)


def test_unfinished_entry_is_warning_in_non_strict_mode():
    curriculum = copy.deepcopy(CURRICULUM)
    curriculum[0]["card_ids"].append("hs-999")
    result = validate(curriculum, [_card()], strict=False)
    assert result.ok
    assert len(result.warnings) == 1
    assert "未完成条目" in result.warnings[0].message


def test_card_not_referenced_by_curriculum_is_error():
    curriculum = copy.deepcopy(CURRICULUM)
    curriculum[0]["card_ids"] = []
    result = validate(curriculum, [_card()], strict=False)
    assert not result.ok
    assert any("未出现在任何 card_ids" in issue.message for issue in result.issues)


def test_choice_answer_must_be_in_options():
    card = _card()
    card["exercises"][0]["answer"] = "Z"
    result = validate(copy.deepcopy(CURRICULUM), [card], strict=True)
    assert not result.ok
    assert any("answer 不在 options 中" in issue.message for issue in result.issues)


def test_multi_answer_must_subset_options():
    card = _card()
    card["exercises"][0] = {
        "id": "hs-001-e1",
        "kind": "multi",
        "stem": "题干",
        "options": ["A", "B"],
        "answer": ["A", "Z"],
        "solution_outline": "因为 A",
    }
    result = validate(copy.deepcopy(CURRICULUM), [card], strict=True)
    assert not result.ok
    assert any("multi 的 answer 含 options 外的元素" in issue.message for issue in result.issues)
