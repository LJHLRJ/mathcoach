"""提示阶梯：升降级规则全部做成纯函数，可单测。"""
from .models import Independence

START_LEVEL = 1          # 默认从 L1 起，不做零提示裸测
MAX_REQUESTED_LEVEL = 4  # 用户说“给步骤/直接给答案”最高到 L4
MAX_LEVEL = 6            # L6 为复述/变式闭环
INDEPENDENT_MAX_LEVEL = 3  # 用到 L4 及以上即记为半独立


def initial_level() -> int:
    return START_LEVEL


def next_level(current: int) -> int:
    """答错一次升一级，封顶 L6。"""
    return min(current + 1, MAX_LEVEL)


def independence_for(max_hint_level: int) -> Independence:
    if max_hint_level > INDEPENDENT_MAX_LEVEL:
        return Independence.SEMI_INDEPENDENT
    return Independence.INDEPENDENT


def grant_requested_level(
    current: int, request: str, attempted_levels: set[int]
) -> tuple[int, str]:
    """处理用户主动请求提示，返回 (新层级, 给用户的一句话说明)。

    M1 中 L5 仅在用户已在 L4 作答过时可达；连错诊断与 L5 的完整触发场景在 M2 补全。
    """
    if request == "step":
        return MAX_REQUESTED_LEVEL, "按你的要求给步骤，最高到 L4。"
    if request == "answer":
        return MAX_REQUESTED_LEVEL, "直接给答案也只到 L4；L5 需要先尝试 L1—L4。"
    if request == "level5":
        if {1, 2, 3, 4}.issubset(attempted_levels):
            return 5, "L1—L4 均已尝试，开放 L5 完整推导。"
        return current, "L5 需要先尝试 L1—L4。"
    raise ValueError(f"未知提示请求：{request}")
