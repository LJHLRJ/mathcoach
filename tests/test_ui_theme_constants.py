"""主题常量回归：常量 CSS、减少动效与注入幂等。"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest

from mathcoach.ui import theme


def test_theme_css_is_constant_and_local():
    css = theme.THEME_CSS

    assert "<style>" in css
    assert "</style>" in css
    assert 'data-testid="stMainBlockContainer"' in css
    assert "st-key-mc-card-" in css
    assert 'button[kind="primary"]' in css
    assert 'button[kind="primaryFormSubmit"]' in css
    assert "prefers-reduced-motion" in css
    assert "<script" not in css.lower()
    assert "http://" not in css.lower()
    assert "https://" not in css.lower()


def test_density_css_only_injects_for_compact():
    assert theme.density_css(theme.DENSITY_COMFORTABLE) == ""
    assert theme.density_css(theme.DENSITY_COMPACT) == (
        theme.COMPACT_DENSITY_CSS
    )
    assert "gap" in theme.COMPACT_DENSITY_CSS
    assert "stVerticalBlock" in theme.COMPACT_DENSITY_CSS


def test_inject_theme_can_be_called_twice():
    at = AppTest.from_string(
        "from mathcoach.ui.theme import inject_theme\n"
        "inject_theme()\n"
        "inject_theme()\n"
    )
    at.run()

    assert not at.exception
