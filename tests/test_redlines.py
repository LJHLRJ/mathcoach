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
    """令牌与 API key 被脱敏。"""
    assert "abc123" not in sanitize_text("token=abc123")
    assert "[已脱敏]" in sanitize_text("token=abc123")
    assert "[已脱敏]" in sanitize_text("api_key: sk-test")
    assert "Bearer" not in sanitize_text("Authorization: Bearer abc.def")


def test_sanitize_phone_id_and_internal_address():
    """手机号、身份证与内网地址被脱敏。"""
    assert sanitize_text("电话 13800138000") == "电话 [已脱敏]"
    assert sanitize_text("身份证 110101199001011234") == "身份证 [已脱敏]"
    assert sanitize_text("服务器 192.168.1.10") == "服务器 [已脱敏]"
    assert sanitize_text("内网 db.internal") == "内网 [已脱敏]"


def test_person_name_only_in_field_context():
    """姓名仅在字段语境下脱敏。"""
    assert sanitize_text("姓名：张三") == "姓名=[已脱敏]"
    assert sanitize_text("题目里的张三不是字段") == "题目里的张三不是字段"


def test_residence_is_redacted():
    """住址字段被脱敏。"""
    assert sanitize_text("住址：幸福小区 3 栋 201") == "住址=[已脱敏]"


def test_payload_sensitive_keys_are_redacted():
    """敏感键与文本内容同时脱敏。"""
    cleaned = sanitize_payload({"token": "abc", "text": "电话 13800138000"})
    assert cleaned["token"] == "[已脱敏]"
    assert cleaned["text"] == "电话 [已脱敏]"


def test_describe_write_is_redacted():
    """写操作摘要脱敏后保留操作名。"""
    summary = describe_write("export", {"api_key": "sk-secret", "note": "导出"})
    assert "export" in summary
    assert "sk-secret" not in summary
    assert "[已脱敏]" in summary


def test_routine_write_allowed_with_consent():
    """有同意时常规写入放行。"""
    assert_write_allowed("receipt", consent=Consent())
    assert_write_allowed("mistake", consent=Consent())


def test_routine_write_blocked_without_consent():
    """缺少同意时常规写入被阻止。"""
    with pytest.raises(WriteBlocked):
        assert_write_allowed("receipt", consent=Consent(memory=False, mistake_book=False))
    with pytest.raises(WriteBlocked):
        assert_write_allowed(
            "mistake", consent=Consent(memory=True, mistake_book=False)
        )


def test_routine_writes_are_auto_approved_even_in_observed_session():
    """观察会话中常规写入仍自动放行。"""
    assert_write_allowed("receipt", consent=Consent(), observed=True)
    assert_write_allowed("mistake", consent=Consent(), observed=True)


def test_export_requires_explicit_confirmation():
    """导出需要完整确认串。"""
    with pytest.raises(ConfirmationRequired):
        assert_write_allowed("export", consent=Consent())
    assert_write_allowed(
        "export", consent=Consent(), confirmation=FULL_CONFIRMATION
    )


def test_export_blocked_when_consent_all_off():
    """同意全关时导出被阻止。"""
    with pytest.raises(WriteBlocked):
        assert_write_allowed(
            "export",
            consent=Consent(memory=False, mistake_book=False),
            confirmation=FULL_CONFIRMATION,
        )


def test_repo_destination_is_always_blocked():
    """目标为仓库时始终阻止写入。"""
    with pytest.raises(WriteBlocked):
        assert_write_allowed(
            "export",
            consent=Consent(),
            confirmation=FULL_CONFIRMATION,
            destination="repo",
        )


def test_unknown_operation_is_blocked():
    """未知操作被阻止。"""
    with pytest.raises(WriteBlocked):
        assert_write_allowed("unknown", consent=Consent())
