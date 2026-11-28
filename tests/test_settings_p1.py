"""P1 设置：调度偏好、凭据文件与连接错误脱敏。"""
import os
from datetime import UTC, datetime

from mathcoach.domain.models import (
    ExerciseKind,
    Independence,
    Receipt,
    Stage,
)
from mathcoach.domain.settings import AppSettings
from mathcoach.memory.settings_repo import (
    SQLiteSettingsStore,
    load_ai_credentials,
    save_ai_credentials,
)
from mathcoach.memory.sqlite_repo import SQLiteRepository
from mathcoach.ui.settings import sanitized_connection_error

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def _receipt() -> Receipt:
    """构造收据样例。"""
    return Receipt(
        card_id="hs-001",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=12,
        max_hint_level=1,
        goal="搞懂函数",
        independence=Independence.INDEPENDENT,
        created_at=NOW,
        exercise_id="ex-1",
    )


def test_advanced_settings_validation_and_mapping():
    """高级设置校验并保留合法值。"""
    settings = AppSettings.from_mapping(
        {
            "scheduler": "sm2",
            "new_review_ratio": 35,
            "font_size": "large",
        }
    )
    assert settings.scheduler == "sm2"
    assert settings.new_review_ratio == 35
    assert settings.font_size == "large"
    assert settings.to_mapping() == {
        "ai_enabled": False,
        "daily_review_limit": 0,
    }
    assert settings.to_mapping(include_advanced=True)["scheduler"] == "sm2"

    invalid = AppSettings.from_mapping(
        {"scheduler": "voodoo", "font_size": "huge", "new_review_ratio": 999}
    )
    assert invalid.scheduler == "fsrs"
    assert invalid.font_size == "medium"
    assert invalid.new_review_ratio == 100


def test_ai_credentials_round_trip_and_clear(tmp_path):
    """凭据文件往返、权限与清空。"""
    path = tmp_path / "secrets.local"
    save_ai_credentials("sk-secret", "https://example.test/v1", path=path)

    assert load_ai_credentials(path) == ("sk-secret", "https://example.test/v1")
    if os.name != "nt":
        assert (path.stat().st_mode & 0o777) == 0o600

    save_ai_credentials("", "", path=path)
    assert not path.exists()
    assert load_ai_credentials(path) == ("", "")


def test_connection_error_does_not_echo_key():
    """连接错误不回显密钥。"""
    message = sanitized_connection_error(
        RuntimeError("invalid api_key=sk-secret"), "sk-secret"
    )

    assert "sk-secret" not in message
    assert "已脱敏" in message


def test_scheduler_change_does_not_rewrite_receipts(tmp_path):
    """切换调度不重写已有收据。"""
    path = tmp_path / "history.sqlite3"
    repository = SQLiteRepository(path)
    receipt = _receipt()
    repository.save_receipt(receipt, receipt.exercise_id)
    store = SQLiteSettingsStore(path)
    try:
        store.set_many({"scheduler": "sm2"})
    finally:
        store.close()

    assert repository.list_receipts(limit=None) == [receipt]
    repository.close()


def test_font_size_change_does_not_rewrite_receipts(tmp_path):
    """切换字号不重写已有收据。"""
    path = tmp_path / "font.sqlite3"
    repository = SQLiteRepository(path)
    receipt = _receipt()
    repository.save_receipt(receipt, receipt.exercise_id)
    store = SQLiteSettingsStore(path)
    try:
        store.set_many({"font_size": "large"})
    finally:
        store.close()

    assert repository.list_receipts(limit=None) == [receipt]
    repository.close()


def test_ai_key_is_not_stored_in_settings_or_export(tmp_path):
    """密钥不进入设置存储或导出。"""
    path = tmp_path / "settings.sqlite3"
    store = SQLiteSettingsStore(path)
    try:
        store.set_many(
            {
                "ai_enabled": True,
                "daily_review_limit": 5,
                "scheduler": "sm2",
                "font_size": "large",
            }
        )
        values = store.get_all()
    finally:
        store.close()

    assert "sk-secret" not in str(values)
    assert "api_key" not in values
    assert values["scheduler"] == "sm2"
    assert values["font_size"] == "large"


def test_advanced_settings_are_loaded_from_store(tmp_path):
    """高级设置可从存储读回。"""
    path = tmp_path / "roundtrip.sqlite3"
    store = SQLiteSettingsStore(path)
    try:
        store.set_many(
            {
                "new_review_ratio": 40,
                "scheduler": "sm2",
                "font_size": "small",
            }
        )
    finally:
        store.close()

    reopened = SQLiteSettingsStore(path)
    try:
        settings = AppSettings.from_mapping(reopened.get_all())
    finally:
        reopened.close()

    assert settings.new_review_ratio == 40
    assert settings.scheduler == "sm2"
    assert settings.font_size == "small"
