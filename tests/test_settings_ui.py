"""设置页 AppTest 冒烟：游客提示与非游客入口。"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import Consent
from mathcoach.memory.sqlite_repo import SQLiteRepository

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _open_settings(path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """打开应用并切换到设置页。"""
    monkeypatch.setenv("MATHCOACH_DB", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()
    return at


def test_settings_page_guest_shows_warning_and_disables_persistent_actions(
    tmp_path, monkeypatch
):
    """游客模式显示提示并禁用持久化操作。"""
    path = tmp_path / "guest.sqlite3"
    repository = SQLiteRepository(path)
    repository.save_consent(Consent(memory=False, mistake_book=False))
    repository.close()

    at = _open_settings(path, monkeypatch)

    assert not at.exception
    assert at.subheader[0].value == "设置"
    assert any("游客模式" in warning.value for warning in at.warning)
    assert any(
        "游客模式没有持久学习数据可导出" in info.value for info in at.info
    )


def test_settings_page_non_guest_has_export_and_clear_sections(
    tmp_path, monkeypatch
):
    """非游客模式展示导出与清除区块。"""
    path = tmp_path / "regular.sqlite3"

    at = _open_settings(path, monkeypatch)

    assert not at.exception
    assert at.subheader[0].value == "设置"
    markdown = " ".join(element.value for element in at.markdown)
    assert "导出学习数据" in markdown
    assert "清除全部学习数据" in markdown
    assert any("本地 SQLite" in caption.value for caption in at.caption)
