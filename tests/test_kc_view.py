"""KC 影子视图：排序、反向卡片映射与薄弱 KC 推荐。"""
from mathcoach.domain.models import (
    Difficulty,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    Stage,
)
from mathcoach.mastery import (
    build_kc_progress,
    kc_card_ids,
    weak_kc_recommendations,
)

KC_F1 = "kc-hs-trig-002-f1"
KC_P1 = "kc-hs-trig-002-p1"
KC_MAP = {
    "a-e1": (KC_F1,),
    "a-e2": (KC_P1,),
}


def _card() -> KnowledgeCard:
    """构造一张带两道题的最小卡片。"""
    return KnowledgeCard(
        id="card-a",
        name="同角三角函数关系",
        stage=Stage.HIGH_SCHOOL,
        course="三角函数",
        chapter="三角",
        difficulty=Difficulty.BASIC,
        intuition="直觉",
        definition="定义",
        mistakes=(),
        example="例子",
        exercises=(
            Exercise(
                id="a-e1",
                card_id="card-a",
                kind=ExerciseKind.EXPR,
                stem="题干一",
                answer="1",
                solution_outline="思路",
            ),
            Exercise(
                id="a-e2",
                card_id="card-a",
                kind=ExerciseKind.FILL,
                stem="题干二",
                answer="4/5",
                solution_outline="思路",
            ),
        ),
        source="",
    )


def test_kc_card_ids_reverse_mapping() -> None:
    """KC 能反向映射到关联卡片。"""
    mapping = kc_card_ids([_card()], KC_MAP)

    assert mapping[KC_F1] == ("card-a",)
    assert mapping[KC_P1] == ("card-a",)


def test_progress_sorted_and_skips_unknown_kc() -> None:
    """按掌握度升序展示，未知 KC 不进入视图。"""
    progress = build_kc_progress(
        [_card()],
        {KC_P1: 0.8, KC_F1: 0.2, "kc-unknown": 0.1},
        sample_sizes={KC_F1: 3},
        kc_map=KC_MAP,
        limit=5,
    )

    assert [item.kc_id for item in progress] == [KC_F1, KC_P1]
    assert progress[0].name == "同角平方关系"
    assert progress[0].sample_size == 3
    assert progress[0].card_ids == ("card-a",)


def test_weak_kc_recommends_card_with_basis() -> None:
    """低于阈值的 KC 转成卡片推荐，并带影子样本与正式 BKT。"""
    recommendations = weak_kc_recommendations(
        [_card()],
        {KC_F1: 0.2, KC_P1: 0.8},
        sample_sizes={KC_F1: 3},
        card_mastery={"card-a": 0.3},
        kc_map=KC_MAP,
    )

    assert len(recommendations) == 1
    assert recommendations[0].card_id == "card-a"
    assert "薄弱 KC" in recommendations[0].reason
    assert "20%" in recommendations[0].basis
    assert "样本 3" in recommendations[0].basis
    assert "卡片 BKT 30%" in recommendations[0].basis


def test_weak_kc_threshold_can_exclude_all() -> None:
    """阈值低于当前掌握度时不产生推荐。"""
    recommendations = weak_kc_recommendations(
        [_card()],
        {KC_F1: 0.2},
        kc_map=KC_MAP,
        threshold=0.1,
    )

    assert recommendations == []
