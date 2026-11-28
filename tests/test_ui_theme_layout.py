"""布局密度接口回归：默认值、持久化与游客模式。"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import Consent
from mathcoach.ui import theme

PERSISTENT = Consent(memory=True, mistake_book=True)


def test_layout_density_persists_in_settings_store(tmp_path):
    """密度在设置存储中读写并拒绝非法值。"""
    path = tmp_path / "layout-density.sqlite3"

    assert theme.load_layout_density(PERSISTENT, path) == (
        theme.DENSITY_COMFORTABLE
    )
    assert theme.save_layout_density(
        PERSISTENT, theme.DENSITY_COMPACT, path
    ) is True
    assert theme.load_layout_density(PERSISTENT, path) == (
        theme.DENSITY_COMPACT
    )
    assert theme.save_layout_density(PERSISTENT, "unknown", path) is False
    assert theme.load_layout_density(PERSISTENT, path) == (
        theme.DENSITY_COMPACT
    )


def test_guest_layout_density_uses_session_state():
    """未授权持久化时密度存入会话状态。"""
    at = AppTest.from_string(
        "from mathcoach.ui import theme\n"
        "theme.layout_density()\n"
        "theme.save_layout_density(None, theme.DENSITY_COMPACT)\n"
    )
    at.run()

    assert not at.exception
    assert at.session_state[theme.LAYOUT_DENSITY_KEY] == (
        theme.DENSITY_COMPACT
    )
