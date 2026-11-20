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
    assert initial_level() == 1


def test_next_level_caps_at_l6():
    assert next_level(1) == 2
    assert next_level(6) == 6


def test_automatic_next_level_caps_at_l4():
    assert automatic_next_level(1) == 2
    assert automatic_next_level(4) == 4  # L5 必须显式请求
    assert automatic_next_level(5) == 5  # 已显式开放，不倒退
    assert automatic_next_level(6) == 6


def test_request_step_caps_at_l4():
    level, message = grant_requested_level(1, "step", {1})
    assert level == 4
    assert "L4" in message


def test_request_answer_caps_at_l4():
    level, message = grant_requested_level(1, "answer", {1})
    assert level == 4
    assert "L4" in message


def test_l5_requires_levels_1_to_4():
    level, message = grant_requested_level(4, "level5", {1, 2, 3})
    assert level == 4
    assert "L1—L4" in message

    level, _ = grant_requested_level(4, "level5", {1, 2, 3, 4})
    assert level == 5


def test_unknown_request_raises():
    with pytest.raises(ValueError):
        grant_requested_level(1, "give_everything", {1})


def test_independence_threshold_is_l4():
    assert independence_for(3) is Independence.INDEPENDENT
    assert independence_for(4) is Independence.SEMI_INDEPENDENT
