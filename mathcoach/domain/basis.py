"""诊断依据：纯函数，只根据显式输入生成可复核文字，不读库、不调模型。"""
from __future__ import annotations

from typing import Protocol


class GapStat(Protocol):
    """先修缺口所需的最小统计形状，避免 basis 反向依赖 prerequisites。"""

    total: int
    concept_wrong: int


def basis_for_receipt(max_hint_level: int, judged: bool, verified: bool) -> str:
    """收据依据：判定结果、符号验证与最高提示层级。

    Args:
        max_hint_level: 本题最高提示层级。
        judged: 是否通过判定；False 直接返回“不生成收据”。
        verified: 符号验证是否通过；False 按半独立记录。

    Returns:
        写入收据 ``basis`` 的一句话。
    """
    if not judged:
        return "未通过判定，不生成收据"
    if not verified:
        # 符号验证未通过时不能把结果当作独立完成
        return "符号验证未通过，按半独立记录"
    if max_hint_level < 4:
        return f"独立完成，最高提示 L{max_hint_level}"
    return f"半独立完成，最高提示 L{max_hint_level}"


def basis_for_gap(stat: GapStat) -> str:
    """先修缺口依据：概念错次数与占比。

    Args:
        stat: 具备 ``total`` 与 ``concept_wrong`` 的统计对象。

    Returns:
        无错题时返回“暂无记录”，否则返回次数与占比。
    """
    if stat.total <= 0:
        return "暂无先修错题记录"
    rate = round(stat.concept_wrong / stat.total * 100)
    return (
        f"前置概念错 {stat.concept_wrong}/{stat.total} 次（{rate}%），"
        "达到缺口阈值"
    )


def basis_for_mastery(
    receipt_count: int,
    wrong_count: int,
    total: int,
    probability: float | None = None,
) -> str:
    """掌握度依据：BKT 概率 + 收据数 + 错题占比。

    Args:
        receipt_count: 该知识点的收据数。
        wrong_count: 该知识点的错题数。
        total: 收据数与错题数之和。
        probability: BKT 掌握概率；None 表示尚未计算。

    Returns:
        展示用的一句话依据。
    """
    if probability is not None:
        return (
            f"掌握概率 {probability:.0%}；收据 {receipt_count} 次，"
            f"错题 {wrong_count}/{total}"
        )
    if total <= 0:
        return f"收据 {receipt_count} 次，暂无错题记录"
    return (
        f"收据 {receipt_count} 次，错题 {wrong_count}/{total}，"
        "按收据与错题综合判断"
    )
