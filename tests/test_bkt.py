"""BKT 纯函数：四参数更新、先验、转移概率与无时钟。"""
from math import isclose

from mathcoach.domain.bkt import (
    DEFAULT_BKT_PARAMS,
    BKTParams,
    initial_mastery,
    update_mastery,
)


def test_initial_mastery():
    assert initial_mastery() == DEFAULT_BKT_PARAMS.p_init


def test_correct_updates_mastery_up():
    prior = 0.3

    posterior = update_mastery(prior, correct=True, params=DEFAULT_BKT_PARAMS)

    assert posterior > prior


def test_wrong_updates_mastery_down():
    prior = 0.7

    posterior = update_mastery(prior, correct=False, params=DEFAULT_BKT_PARAMS)

    assert posterior < prior


def test_transit_after_update():
    params_without_transit = BKTParams(
        p_init=DEFAULT_BKT_PARAMS.p_init,
        p_transit=0.0,
        p_guess=DEFAULT_BKT_PARAMS.p_guess,
        p_slip=DEFAULT_BKT_PARAMS.p_slip,
    )

    with_transit = update_mastery(0.5, correct=True, params=DEFAULT_BKT_PARAMS)
    without_transit = update_mastery(0.5, correct=True, params=params_without_transit)

    assert with_transit > without_transit


def test_pure_no_clock_and_deterministic():
    import mathcoach.domain.bkt as bkt

    assert not hasattr(bkt, "datetime")
    assert not hasattr(bkt, "time")

    first = update_mastery(0.4, correct=True, params=DEFAULT_BKT_PARAMS)
    second = update_mastery(0.4, correct=True, params=DEFAULT_BKT_PARAMS)

    assert isclose(first, second)
