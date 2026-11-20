"""安全层：注入守卫与写操作红线。"""
from .guards import (
    REFUSAL_TEXT,
    Blocked,
    check_parsed_answer,
    detect_injection,
    detect_math_framing,
)
from .redlines import (
    FULL_CONFIRMATION,
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
    describe_write,
    sanitize_text,
)

__all__ = [
    "REFUSAL_TEXT",
    "FULL_CONFIRMATION",
    "Blocked",
    "ConfirmationRequired",
    "WriteBlocked",
    "assert_write_allowed",
    "check_parsed_answer",
    "describe_write",
    "detect_injection",
    "detect_math_framing",
    "sanitize_text",
]
