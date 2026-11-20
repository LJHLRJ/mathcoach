"""写操作红线：同意、观察状态、逐次确认、禁止仓库写入与脱敏。"""
import pytest

from mathcoach.domain.models import Consent
from mathcoach.safety.redlines import (
    FULL_CONFIRMATION,
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
    describe_write,
    sanitize_payload,
    sanitize_text,
)


def test_sanitize_token_and_api_key():
    assert "abc123" not in sanitize_text("token=abc123")
    assert "[已脱敏]" in sanitize_text("token=abc123")
    assert "[已脱敏]" in sanitize_text("api_key: sk-test")
    assert "Bearer" not in sanitize_text("Authorization: Bearer abc.def")


def test_sanitize_phone_id_and_internal_address():
    assert sanitize_text("电话 13800138000") == "电话 [已脱敏]"
    assert sanitize_text("身份证 110101199001011234") == "身份证 [已脱敏]"
    assert sanitize_text("服务器 192.168.1.10") == "服务器 [已脱敏]"
    assert sanitize_text("内网 db.internal") == "内网 [已脱敏]"


def test_person_name_only_in_field_context():
    assert sanitize_text("姓名：张三") == "姓名=[已脱敏]"
    assert sanitize_text("题目里的张三不是字段") == "题目里的张三不是字段"


def test_residence_is_redacted():
    assert sanitize_text("住址：幸福小区 3 栋 201") == "住址=[已脱敏]"


def test_payload_sensitive_keys_are_redacted():
    cleaned = sanitize_payload({"token": "abc", "text": "电话 13800138000"})
    assert cleaned["token"] == "[已脱敏]"
    assert cleaned["text"] == "电话 [已脱敏]"


def test_describe_write_is_redacted():
    summary = describe_write("export", {"api_key": "sk-secret", "note": "导出"})
    assert "export" in summary
    assert "sk-secret" not in summary
    assert "[已脱敏]" in summary


def test_routine_write_allowed_with_consent():
    assert_write_allowed("receipt", consent=Consent())
    assert_write_allowed("mistake", consent=Consent())


def test_routine_write_blocked_without_consent():
    with pytest.raises(WriteBlocked):
        assert_write_allowed("receipt", consent=Consent(memory=False, mistake_book=False))
    with pytest.raises(WriteBlocked):
        assert_write_allowed(
            "mistake", consent=Consent(memory=True, mistake_book=False)
        )


def test_routine_writes_are_auto_approved_even_in_observed_session():
    assert_write_allowed("receipt", consent=Consent(), observed=True)
    assert_write_allowed("mistake", consent=Consent(), observed=True)


def test_export_requires_explicit_confirmation():
    with pytest.raises(ConfirmationRequired):
        assert_write_allowed("export", consent=Consent())
    assert_write_allowed(
        "export", consent=Consent(), confirmation=FULL_CONFIRMATION
    )


def test_export_blocked_when_consent_all_off():
    with pytest.raises(WriteBlocked):
        assert_write_allowed(
            "export",
            consent=Consent(memory=False, mistake_book=False),
            confirmation=FULL_CONFIRMATION,
        )


def test_repo_destination_is_always_blocked():
    with pytest.raises(WriteBlocked):
        assert_write_allowed(
            "export",
            consent=Consent(),
            confirmation=FULL_CONFIRMATION,
            destination="repo",
        )


def test_unknown_operation_is_blocked():
    with pytest.raises(WriteBlocked):
        assert_write_allowed("unknown", consent=Consent())
