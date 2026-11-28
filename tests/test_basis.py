"""依据生成：收据、先修缺口、掌握度的纯函数文字。"""
from mathcoach.domain.basis import (
    basis_for_gap,
    basis_for_mastery,
    basis_for_receipt,
)
from mathcoach.domain.prerequisites import MistakeStat


def test_receipt_basis_independent():
    """无提示独立完成时记为独立完成 L1。"""
    assert basis_for_receipt(1, judged=True, verified=True) == "独立完成，最高提示 L1"


def test_receipt_basis_semi():
    """最高提示 L4 时记为半独立完成。"""
    assert basis_for_receipt(4, judged=True, verified=True) == "半独立完成，最高提示 L4"


def test_receipt_basis_wrong():
    """判定或符号验证未过时依据明确标注。"""
    assert "未通过判定" in basis_for_receipt(2, judged=False, verified=True)
    # 符号验证未通过时不能按独立完成记录
    assert "符号验证" in basis_for_receipt(1, judged=True, verified=False)


def test_gap_basis():
    """缺口依据包含概念错题比例。"""
    text = basis_for_gap(MistakeStat(total=4, concept_wrong=2))

    assert "2/4" in text
    assert "50%" in text


def test_gap_basis_multiple_parents():
    """不同错题统计分别生成对应比例。"""
    first = basis_for_gap(MistakeStat(total=2, concept_wrong=2))
    second = basis_for_gap(MistakeStat(total=5, concept_wrong=1))

    assert first != second
    assert "2/2" in first
    assert "1/5" in second


def test_mastery_basis():
    """掌握度依据包含收据次数与正确比例。"""
    text = basis_for_mastery(receipt_count=6, wrong_count=1, total=3)

    assert "收据 6 次" in text
    assert "1/3" in text
