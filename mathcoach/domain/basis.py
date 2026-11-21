"""诊断依据：纯函数，只根据显式输入生成可复核文字，不读库、不调模型。"""
from __future__ import annotations

from typing import Protocol


class GapStat(Protocol):
    """先修缺口所需的最小统计形状，避免 basis 反向依赖 prerequisites。"""

    total: int
    concept_wrong: int


def basis_for_receipt(max_hint_level: int, judged: bool, verified: bool) -> str:
    """收据依据：判定结果、符号验证与最高提示层级。"""
    if not judged:
        return "未通过判定，不生成收据"
    if not verified:
        # 符号验证未通过时不能把结果当作独立完成
        return "符号验证未通过，按半独立记录"
    if max_hint_level < 4:
        return f"独立完成，最高提示 L{max_hint_level}"
    return f"半独立完成，最高提示 L{max_hint_level}"


def basis_for_gap(stat: GapStat) -> str:
    """先修缺口依据：概念错次数与占比。"""
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
    """掌握度依据：BKT 概率 + 收据数 + 错题占比。"""
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
