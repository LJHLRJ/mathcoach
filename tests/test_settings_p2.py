"""P2 设置：审计导出、主题与提醒校验及只读面板。"""
from datetime import UTC, datetime
from pathlib import Path

import streamlit.testing.v1 as st_test

from mathcoach.domain.models import AuditEntry
from mathcoach.domain.settings import (
    AppSettings,
    export_audit_csv,
    export_audit_json,
)
from mathcoach.memory.sqlite_repo import SQLiteRepository

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def test_theme_and_reminder_validation():
    """主题与提醒时间合法时保留，非法时回退默认。"""
    settings = AppSettings.from_mapping(
        {
            "theme": "dark",
            "reminder_enabled": True,
            "reminder_time": "21:30",
        }
    )
    assert settings.theme == "dark"
    assert settings.reminder_enabled is True
    assert settings.reminder_time == "21:30"
    advanced = settings.to_mapping(include_advanced=True)
    assert advanced["theme"] == "dark"
    assert advanced["reminder_time"] == "21:30"

    invalid = AppSettings.from_mapping(
        {"theme": "neon", "reminder_time": "99:99"}
    )
    assert invalid.theme == "light"
    assert invalid.reminder_time == "08:00"


def test_audit_export_redacts_sensitive_text():
    """审计导出会脱敏敏感文本。"""
    entry = AuditEntry(
        id=1,
        op="settings_clear",
        result="token=sk-secret",
        created_at=NOW,
    )
    csv_text = export_audit_csv([entry])
    json_text = export_audit_json([entry], NOW)

    assert "sk-secret" not in csv_text
    assert "sk-secret" not in json_text
    assert "已脱敏" in csv_text
    assert "已脱敏" in json_text


def test_settings_page_has_read_only_audit_and_dev_panels(
    tmp_path, monkeypatch
):
    """设置页提供只读审计与开发者面板及说明。"""
    path = tmp_path / "p2.sqlite3"
    repository = SQLiteRepository(path)
    repository.record_audit("seed", "ok")
    repository.close()
    monkeypatch.setenv("MATHCOACH_DB", str(path))

    at = st_test.AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    markdown = " ".join(element.value for element in at.markdown)
    captions = " ".join(element.value for element in at.caption)
    expanders = " ".join(element.label for element in at.expander)
    assert "安全审计日志（只读）" in markdown
    assert "开发者信息（只读）" in expanders
    assert "查看审计日志" in expanders
    assert "本面板只读，不提供写入口。" in captions
    assert "主题需重启应用" in " ".join(
        element.value for element in at.caption
    )
    assert "提醒仅在应用打开时生效" in " ".join(
        element.value for element in at.caption
    )
