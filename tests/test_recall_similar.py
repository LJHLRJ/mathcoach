"""相似题召回：去重限量、KC/错因排序、迁移题与空召回降级。"""
from mathcoach.domain.models import (
    Difficulty,
    ErrorType,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    Stage,
)
from mathcoach.recall import RecallQuery, recall_similar
from mathcoach.recall.similar import _fallback


def _exercise(
    exercise_id: str,
    card_id: str,
    kind: ExerciseKind,
    stem: str,
    answer: str = "答案",
) -> Exercise:
    """构造一道最小题目。"""
    return Exercise(
        id=exercise_id,
        card_id=card_id,
        kind=kind,
        stem=stem,
        answer=answer,
        solution_outline="标准思路",
    )


def _card(
    card_id: str,
    chapter: str,
    exercises: tuple[Exercise, ...],
    *,
    course: str = "函数与导数",
) -> KnowledgeCard:
    """构造一张最小知识点卡。"""
    return KnowledgeCard(
        id=card_id,
        name=card_id,
        stage=Stage.HIGH_SCHOOL,
        course=course,
        chapter=chapter,
        difficulty=Difficulty.BASIC,
        intuition="直觉",
        definition="定义",
        mistakes=(),
        example="例子",
        exercises=exercises,
        source="测试",
    )


def test_recall_limits_dedupes_and_excludes_source() -> None:
    """召回去重、限量并排除源题。"""
    source = _exercise(
        "a-e1",
        "card-a",
        ExerciseKind.CHOICE,
        "下列对应关系中，y 是 x 的函数的是",
    )
    siblings = (
        _exercise(
            "a-e2",
            "card-a",
            ExerciseKind.FILL,
            "求 f(x)=1/(x−1) 的定义域",
        ),
        _exercise(
            "a-e3",
            "card-a",
            ExerciseKind.TRUEFALSE,
            "f(x)=x² 与 g(x)=x 的定义域相同",
        ),
    )
    others = tuple(
        _exercise(f"b-e{index}", "card-b", ExerciseKind.CHOICE, f"同章节选择题 {index}")
        for index in range(1, 6)
    )
    cards = [
        _card("card-a", "函数概念", (source, *siblings)),
        _card("card-b", "函数概念", others),
        _card("card-a-copy", "函数概念", (siblings[0],)),
    ]

    result = recall_similar(
        RecallQuery(source, "card-a", ErrorType.CONCEPT), cards
    )

    ids = [candidate.exercise.id for candidate in result.candidates]
    assert 3 <= len(ids) <= 5
    assert len(ids) == len(set(ids))
    assert "a-e1" not in ids
    assert ids.count("a-e2") == 1


def test_recall_prefers_shared_kc_over_chapter() -> None:
    """共享细粒度 KC 的题目优先于只同章节的题目。"""
    source = _exercise(
        "a-e1", "card-a", ExerciseKind.CHOICE, "已知 sin x=3/5，求 cos x"
    )
    sibling = _exercise(
        "a-e2", "card-a", ExerciseKind.FILL, "化简 sin²x+cos²x"
    )
    kc_match = _exercise(
        "c-e1", "card-c", ExerciseKind.EXPR, "若 cos x=−4/5，求 sin x"
    )
    chapter_match = _exercise(
        "b-e1", "card-b", ExerciseKind.CHOICE, "函数的定义域是什么"
    )
    cards = [
        _card("card-a", "三角恒等变换", (source, sibling), course="三角函数"),
        _card("card-b", "三角恒等变换", (chapter_match,), course="三角函数"),
        _card("card-c", "三角恒等变换", (kc_match,), course="三角函数"),
    ]

    result = recall_similar(
        RecallQuery(source, "card-a", ErrorType.FORMULA),
        cards,
        kc_map={"a-e1": ("kc-1",), "c-e1": ("kc-1",)},
    )

    candidates = {item.exercise.id: item for item in result.candidates}
    assert "共享 KC" in candidates["c-e1"].reasons
    assert candidates["c-e1"].score > candidates["b-e1"].score


def test_recall_uses_error_type_kind_preference() -> None:
    """公式错因偏好填空/表达式题。"""
    source = _exercise(
        "a-e1", "card-a", ExerciseKind.CHOICE, "已知 sin x=3/5，求 cos x"
    )
    fill = _exercise(
        "b-e1", "card-b", ExerciseKind.FILL, "求 cos 60° 的值"
    )
    truefalse = _exercise(
        "b-e2",
        "card-b",
        ExerciseKind.TRUEFALSE,
        "判断 sin²x+cos²x=1 是否恒成立",
    )
    cards = [
        _card("card-a", "三角恒等变换", (source,), course="三角函数"),
        _card(
            "card-b",
            "三角恒等变换",
            (fill, truefalse),
            course="三角函数",
        ),
    ]

    result = recall_similar(
        RecallQuery(source, "card-a", ErrorType.FORMULA), cards
    )

    candidates = {item.exercise.id: item for item in result.candidates}
    assert "匹配错因" in candidates["b-e1"].reasons
    assert "匹配错因" not in candidates["b-e2"].reasons
    assert candidates["b-e1"].score > candidates["b-e2"].score


def test_recall_forces_structural_transfer() -> None:
    """迁移题分数较低时也会被选入召回集。"""
    source = _exercise(
        "a-e1",
        "card-a",
        ExerciseKind.CHOICE,
        "下列对应关系中，y 是 x 的函数的是",
    )
    same_card = tuple(
        _exercise(f"a-e{index}", "card-a", ExerciseKind.CHOICE, f"同卡选择题 {index}")
        for index in (2, 3)
    )
    chapter_choices = tuple(
        _exercise(
            f"b-c{index}", "card-b", ExerciseKind.CHOICE, f"同章节选择题 {index}"
        )
        for index in range(1, 6)
    )
    transfer = _exercise(
        "b-t1", "card-b", ExerciseKind.FILL, "求 f(x)=1/(x−1) 的定义域"
    )
    cards = [
        _card("card-a", "函数概念", (source, *same_card)),
        _card("card-b", "函数概念", (*chapter_choices, transfer)),
    ]

    result = recall_similar(
        RecallQuery(source, "card-a", ErrorType.CONCEPT), cards, limit=3
    )

    assert any(candidate.is_transfer for candidate in result.candidates)
    assert result.transfer_missing is False


def test_recall_empty_result_is_non_blocking() -> None:
    """没有可召回题目时返回空结果并标记降级。"""
    source = _exercise(
        "only-e1", "card-only", ExerciseKind.CHOICE, "唯一题目"
    )
    card = _card("card-only", "独立章节", (source,))

    result = recall_similar(
        RecallQuery(source, "card-only", ErrorType.CONCEPT), [card]
    )

    assert result.candidates == ()
    assert result.fallback_used is True
    assert result.transfer_missing is True
    assert "no_similar" in result.notes


def test_fallback_recommends_uncompleted_same_card() -> None:
    """降级推荐排除已做题，只保留同卡未做题。"""
    source = _exercise("a-e1", "card-a", ExerciseKind.CHOICE, "源题")
    done = _exercise("a-e2", "card-a", ExerciseKind.FILL, "已做题")
    fresh = _exercise("a-e3", "card-a", ExerciseKind.TRUEFALSE, "未做题")
    card = _card("card-a", "函数概念", (source, done, fresh))
    query = RecallQuery(
        source,
        "card-a",
        ErrorType.CONCEPT,
        completed_exercise_ids=frozenset({"a-e2"}),
    )

    candidates = _fallback(
        query,
        [card],
        source_card=card,
        kc_map={},
        tree=None,
        limit=5,
    )

    ids = [candidate.exercise.id for candidate in candidates]
    assert "a-e2" not in ids
    assert "a-e3" in ids
