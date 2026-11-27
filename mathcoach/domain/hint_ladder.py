"""提示阶梯：L1–L6 的起始层级、答错升级、主动请求与独立度判定。

纯函数，不读库、不读时钟、不调模型；提示正文由 session.engine 组装。
自动升级最高到 L4，显式请求 L5 需先走完 L1–L4。
"""
from .models import Independence

START_LEVEL = 1          # 默认从 L1 起，不做零提示裸测
MAX_REQUESTED_LEVEL = 4  # 学生要“步骤/答案”时最高到 L4
MAX_LEVEL = 6            # L6 为复述/变式闭环
INDEPENDENT_MAX_LEVEL = 3  # 用到 L4 及以上即记为半独立


def initial_level() -> int:
    """返回每道新题的起始提示层级。

    固定从 L1 起，不做零提示裸测；换题时 session.engine 会重新调用，不跨题继承。

    Returns:
        起始层级，当前恒为 ``START_LEVEL``（1）。
    """
    return START_LEVEL


def next_level(current: int) -> int:
    """答错一次升一级，封顶 L6。

    Args:
        current: 当前层级，引擎传入 1–6。

    Returns:
        升级后的层级，最大 ``MAX_LEVEL``（6）。
    """
    return min(current + 1, MAX_LEVEL)


def automatic_next_level(current: int) -> int:
    """答错后的自动升级：只升不降，封顶 L4。

    L5 只能由学生显式请求（``grant_requested_level``）；当前层级高于 L4 时保持不变。

    Args:
        current: 当前层级。

    Returns:
        ``current`` ≤ 4 时返回 ``min(current + 1, 4)``，否则原样返回。
    """
    return max(current, min(next_level(current), MAX_REQUESTED_LEVEL))


def independence_for(max_hint_level: int) -> Independence:
    """按本次作答的最高提示层级判定独立程度。

    ≤ 3 记为独立完成，≥ 4 记为半独立；只看最高层级，不看中途降级或重试次数。

    Args:
        max_hint_level: 本次作答实际用到的最高层级。

    Returns:
        ``Independence.INDEPENDENT`` 或 ``Independence.SEMI_INDEPENDENT``。
    """
    if max_hint_level > INDEPENDENT_MAX_LEVEL:
        return Independence.SEMI_INDEPENDENT
    return Independence.INDEPENDENT


def grant_requested_level(
    current: int, request: str, attempted_levels: set[int]
) -> tuple[int, str]:
    """处理学生主动请求的提示层级，返回新层级和一句说明。

    ``step`` / ``answer`` 最多展示 L4，且不降低当前层级；``level5`` 要求
    L1–L4 都提交过作答，否则保持当前层级。只做门槛判定，不生成提示正文。

    Args:
        current: 当前层级；``level5`` 未达门槛时原样返回。
        request: ``"step"``、``"answer"`` 或 ``"level5"``。
        attempted_levels: 已提交作答时所在的层级集合，不是点过提示的记录。

    Returns:
        ``(新层级, 说明)``。``level5`` 未达门槛时层级不变，说明提示先试 L1–L4。

    Raises:
        ValueError: ``request`` 不是上述三种取值之一。

    Note:
        ``current`` > 4 时 ``step`` / ``answer`` 返回 ``current``，不把层级退回 L4；
        页面只展示 L4 文案。
    """
    if request == "step":
        return max(current, MAX_REQUESTED_LEVEL), "按你的要求给步骤，最高到 L4。"
    if request == "answer":
        return max(current, MAX_REQUESTED_LEVEL), "直接给答案也只到 L4；L5 需要先尝试 L1—L4。"
    if request == "level5":
        if {1, 2, 3, 4}.issubset(attempted_levels):
            return 5, "L1—L4 均已尝试，开放 L5 完整推导。"
        return current, "L5 需要先尝试 L1—L4。"
    raise ValueError(f"未知提示请求：{request}")
