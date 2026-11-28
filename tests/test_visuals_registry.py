"""可视化注册表：按 card_id / kc_id 返回组件，未知 ID 返回 None。"""
from mathcoach.ui.visuals import registry
from mathcoach.ui.visuals.registry import (
    get_kc_visual,
    get_visual,
    kc_visuals_for_exercises,
    render_kc_visual,
)


def test_known_cards_return_components():
    """已登记的卡片返回可调用的可视化组件。"""
    assert callable(get_visual("hs-func-004"))
    assert callable(get_visual("ug-linear-004"))
    assert callable(get_visual("hs-trig-002"))


def test_unknown_card_returns_none():
    """未登记的卡片返回 None。"""
    assert get_visual("unknown-card") is None


def test_registry_never_raises():
    """空串与正常卡号都不会触发异常。"""
    assert get_visual("") is None
    assert get_visual("hs-func-004") is not None


def test_known_kcs_return_components():
    """已登记的 KC 返回动态讲解组件。"""
    assert callable(get_kc_visual("kc-hs-trig-002-p1"))
    assert callable(get_kc_visual("kc-hs-trig-003-f1"))
    assert callable(get_kc_visual("kc-hs-trig-004-f1"))


def test_unknown_kc_returns_none():
    """未登记的 KC 返回 None。"""
    assert get_kc_visual("kc-hs-trig-002-f1") is None
    assert get_kc_visual("unknown-kc") is None
    assert get_kc_visual("") is None


def test_kc_visuals_for_exercises_filters_and_dedupes():
    """按题目顺序去重，只保留已登记且存在的 KC。"""
    assert kc_visuals_for_exercises(
        ["hs-trig-002-e2", "hs-trig-002-e2", "unknown-exercise"]
    ) == (("kc-hs-trig-002-p1", "象限符号判定"),)
    assert kc_visuals_for_exercises(["hs-trig-003-e1"]) == (
        ("kc-hs-trig-003-f1", "补角公式"),
    )
    assert kc_visuals_for_exercises(["hs-trig-004-e1"]) == (
        ("kc-hs-trig-004-f1", "振幅与周期公式"),
    )


def test_render_kc_visual_failure_is_contained(monkeypatch):
    """组件渲染异常返回 failed，不向调用方抛出。"""

    def boom() -> None:
        """模拟渲染崩溃。"""
        raise RuntimeError("boom")

    monkeypatch.setitem(
        registry._KC_VISUALS, "kc-test-boom", boom
    )

    assert registry.render_kc_visual("kc-test-boom") == "failed"
    assert render_kc_visual("unknown-kc") == "none"
