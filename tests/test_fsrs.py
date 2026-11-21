"""FSRS 纯函数：初始状态、稳定性更新、间隔反解与无时钟纯函数。"""
from pathlib import Path

import yaml

from mathcoach.domain.fsrs import (
    DEFAULT_PARAMS,
    MemoryState,
    Rating,
    initial_state,
    interval_from_retrievability,
    params_from_mapping,
    review,
)

ROOT = Path(__file__).resolve().parents[1]


def test_initial_state():
    again = initial_state(Rating.AGAIN)
    hard = initial_state(Rating.HARD)
    good = initial_state(Rating.GOOD)
    easy = initial_state(Rating.EASY)

    assert again.stability < hard.stability < good.stability < easy.stability
    assert again.lapses == 1
    assert good.lapses == 0
    assert good.reps == 1
    assert 1 <= good.difficulty <= 10


def test_again_resets_stability():
    state = MemoryState(stability=30.0, difficulty=5.0, reps=5, lapses=1)

    new_state, interval = review(state, Rating.AGAIN, elapsed_days=10, params=DEFAULT_PARAMS)

    assert new_state.stability < state.stability
    assert new_state.lapses == state.lapses + 1
    assert new_state.reps == state.reps + 1
    assert interval >= 1


def test_easy_increases_stability():
    state = MemoryState(stability=10.0, difficulty=5.0, reps=3, lapses=0)

    good_state, good_interval = review(state, Rating.GOOD, 5, DEFAULT_PARAMS)
    easy_state, easy_interval = review(state, Rating.EASY, 5, DEFAULT_PARAMS)

    assert easy_state.stability > good_state.stability > state.stability
    assert easy_interval >= good_interval


def test_interval_from_retrievability():
    # desired_retention=0.9 时，间隔应接近 stability 本身
    assert 9 <= interval_from_retrievability(10.0, 0.9) <= 11
    # 目标保持率越高，允许的间隔越短
    assert interval_from_retrievability(10.0, 0.95) < interval_from_retrievability(10.0, 0.9)
    # 非正 stability 仍需至少 1 天
    assert interval_from_retrievability(0.0, 0.9) == 1


def test_pure_function_no_clock():
    import mathcoach.domain.fsrs as fsrs

    # 模块不导入时钟，review 的输出只由显式输入决定
    assert not hasattr(fsrs, "datetime")
    assert not hasattr(fsrs, "time")

    state = initial_state(Rating.GOOD)
    first = review(state, Rating.GOOD, 3, DEFAULT_PARAMS)
    second = review(state, Rating.GOOD, 3, DEFAULT_PARAMS)

    assert first == second
    # 不修改传入的不可变状态
    assert state == initial_state(Rating.GOOD)


def test_params_file_matches_defaults():
    data = yaml.safe_load((ROOT / "content/fsrs_params.yaml").read_text(encoding="utf-8"))

    params = params_from_mapping(data)

    assert params == DEFAULT_PARAMS
    assert params.desired_retention == 0.9
    assert len(params.weights) == 17
