"""收据生成时同步写入依据，避免事后补算。"""
from mathcoach.domain.basis import basis_for_receipt
from mathcoach.domain.models import (
    Difficulty,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    Stage,
)
from mathcoach.domain.receipt import assess_restatement, build_receipt


def _card_and_exercise():
    exercise = Exercise(
        id="hs-001-e1",
        card_id="hs-001",
        kind=ExerciseKind.CHOICE,
        stem="题干",
        answer="A",
        solution_outline="思路",
        options=("A", "B"),
    )
    card = KnowledgeCard(
        id="hs-001",
        name="函数",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        chapter="函数概念",
        difficulty=Difficulty.BASIC,
        intuition="",
        definition="",
        mistakes=(),
        example="",
        exercises=(exercise,),
        source="智能体生成",
    )
    return card, exercise


def test_receipt_has_independent_basis():
    card, exercise = _card_and_exercise()

    receipt = build_receipt(card, exercise, "目标", max_hint_level=1, duration_s=10)

    assert receipt.basis == basis_for_receipt(1, judged=True, verified=True)


def test_receipt_has_semi_independent_basis():
    card, exercise = _card_and_exercise()

    receipt = build_receipt(card, exercise, "目标", max_hint_level=4, duration_s=10)

    assert "半独立完成" in receipt.basis


def test_receipt_records_unverified_basis():
    card, exercise = _card_and_exercise()

    receipt = build_receipt(
        card, exercise, "目标", max_hint_level=1, duration_s=10, verified=False
    )

    assert "符号验证" in receipt.basis


def test_restatement_quality_uses_key_fragment_coverage():
    reference = "根号内非负，即 x−2≥0。"

    assert (
        assess_restatement("根号内非负，所以 x 要大于等于 2", reference)
        == "完整"
    )
    assert assess_restatement("根号里面的数要大于等于 0", reference) == "部分"
    assert assess_restatement("先移项再合并同类项", reference) == "待补充"
    assert assess_restatement("   ", reference) is None
