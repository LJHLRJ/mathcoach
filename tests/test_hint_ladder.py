"""提示阶梯是规范里最硬的可验证规则，必须逐条覆盖。"""
import pytest

from mathcoach.domain.hint_ladder import (
    automatic_next_level,
    grant_requested_level,
    independence_for,
    initial_level,
    next_level,
)
from mathcoach.domain.models import Independence


def test_initial_level_is_l1():
    """初始提示等级为 L1。"""
    assert initial_level() == 1


def test_next_level_caps_at_l6():
    """逐级提示最高到 L6。"""
    assert next_level(1) == 2
    assert next_level(6) == 6


def test_automatic_next_level_caps_at_l4():
    """自动升级止于 L4，已开放等级保持不变。"""
    assert automatic_next_level(1) == 2
    assert automatic_next_level(4) == 4  # L5 必须显式请求
    assert automatic_next_level(5) == 5  # 已显式开放，不倒退
    assert automatic_next_level(6) == 6


def test_request_step_caps_at_l4():
    """请求分步提示最高到 L4。"""
    level, message = grant_requested_level(1, "step", {1})
    assert level == 4
    assert "L4" in message


def test_request_answer_caps_at_l4():
    """请求答案提示最高到 L4。"""
    level, message = grant_requested_level(1, "answer", {1})
    assert level == 4
    assert "L4" in message


def test_request_step_keeps_current_level_above_l4():
    """已高于 L4 时请求不会降级。"""
    level, _ = grant_requested_level(5, "step", {1, 2, 3, 4})
    assert level == 5

    level, _ = grant_requested_level(5, "answer", {1, 2, 3, 4})
    assert level == 5


def test_l5_requires_levels_1_to_4():
    """L5 需要前四级均已开放。"""
    level, message = grant_requested_level(4, "level5", {1, 2, 3})
    assert level == 4
    assert "L1—L4" in message

    level, _ = grant_requested_level(4, "level5", {1, 2, 3, 4})
    assert level == 5


def test_unknown_request_raises():
    """未知请求类型抛出 ValueError。"""
    with pytest.raises(ValueError):
        grant_requested_level(1, "give_everything", {1})


def test_independence_threshold_is_l4():
    """最高提示 L3 视为独立，L4 视为半独立。"""
    assert independence_for(3) is Independence.INDEPENDENT
    assert independence_for(4) is Independence.SEMI_INDEPENDENT
