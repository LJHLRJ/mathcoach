"""可视化注册表：按 card_id 返回组件，未知卡返回 None 且不抛异常。"""
from mathcoach.ui.visuals.registry import get_visual


def test_known_cards_return_components():
    assert callable(get_visual("hs-func-004"))
    assert callable(get_visual("ug-linear-004"))


def test_unknown_card_returns_none():
    assert get_visual("unknown-card") is None


def test_registry_never_raises():
    assert get_visual("") is None
    assert get_visual("hs-func-004") is not None
