"""按钮层级与加载占位常量回归。"""
from __future__ import annotations

import inspect

import streamlit as st
from streamlit.testing.v1 import AppTest

from mathcoach.ui import components


def test_streamlit_supports_skeleton_and_parallel_fragment():
    assert hasattr(st, "skeleton")
    assert "parallel" in inspect.signature(st.fragment).parameters


def test_button_roles_map_to_streamlit_types():
    assert components.BUTTON_TYPES == {
        components.PRIMARY: "primary",
        components.SECONDARY: "secondary",
        components.DANGER: "secondary",
    }
    assert components.button_kwargs(components.PRIMARY) == {"type": "primary"}
    assert components.button_kwargs(components.DANGER) == {
        "type": "secondary"
    }
    assert components.button_kwargs("unknown") == {"type": "secondary"}


def test_danger_css_is_constant_and_targets_clear_button():
    css = components.DANGER_CSS

    assert components.DANGER_KEY in css
    assert ".st-key-" in css
    assert "<script" not in css.lower()
    assert "http://" not in css.lower()
    assert "https://" not in css.lower()


def test_skeleton_heights_are_positive():
    assert len(components.SKELETON_HEIGHTS) == 3
    assert all(value > 0 for value in components.SKELETON_HEIGHTS.values())


def test_loading_skeleton_context_manager_runs():
    at = AppTest.from_string(
        "import streamlit as st\n"
        "from mathcoach.ui.components import loading_skeleton\n"
        "with loading_skeleton():\n"
        "    st.write('loaded')\n"
    )
    at.run()

    assert not at.exception
