"""BKT 纯函数：四参数更新、先验、转移概率与无时钟。"""
from math import isclose

from mathcoach.domain.bkt import (
    DEFAULT_BKT_PARAMS,
    BKTParams,
    initial_mastery,
    update_mastery,
)
from mathcoach.domain.spaced_repetition import Quality


def test_initial_mastery():
    """初始掌握度等于先验参数。"""
    assert initial_mastery() == DEFAULT_BKT_PARAMS.p_init


def test_correct_updates_mastery_up():
    """答对提升掌握概率。"""
    prior = 0.3

    posterior = update_mastery(prior, correct=True, params=DEFAULT_BKT_PARAMS)

    assert posterior > prior


def test_wrong_updates_mastery_down():
    """答错降低掌握概率。"""
    prior = 0.7

    posterior = update_mastery(prior, correct=False, params=DEFAULT_BKT_PARAMS)

    assert posterior < prior


def test_transit_after_update():
    """更新后应用转移概率。"""
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
    """纯函数无时钟依赖且结果确定。"""
    import mathcoach.domain.bkt as bkt

    assert not hasattr(bkt, "datetime")
    assert not hasattr(bkt, "time")

    first = update_mastery(0.4, correct=True, params=DEFAULT_BKT_PARAMS)
    second = update_mastery(0.4, correct=True, params=DEFAULT_BKT_PARAMS)

    assert isclose(first, second)


def test_hinted_correct_gains_less_than_independent():
    """有提示答对带来的增益小于独立答对。"""
    independent = update_mastery(0.3, correct=True, params=DEFAULT_BKT_PARAMS)
    hinted = update_mastery(
        0.3,
        correct=True,
        params=DEFAULT_BKT_PARAMS,
        quality=Quality.HINTED,
    )
    labelled = update_mastery(
        0.3,
        correct=True,
        params=DEFAULT_BKT_PARAMS,
        quality=Quality.INDEPENDENT,
    )

    assert hinted > 0.3
    assert independent > hinted
    assert labelled == independent
