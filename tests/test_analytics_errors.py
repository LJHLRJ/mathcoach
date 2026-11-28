"""错因子类注册表与收敛规则。"""
from mathcoach.analytics import (
    DEFAULT_CODE_BY_ERROR_TYPE,
    ERROR_CODE_SPECS,
    ErrorCode,
    coerce_error_code,
    default_error_code,
    error_type_for_code,
)
from mathcoach.domain.models import ErrorType


def test_every_error_type_has_a_default_code():
    """五类顶层错因都有默认子类。"""
    assert set(DEFAULT_CODE_BY_ERROR_TYPE) == set(ErrorType)
    for error_type in ErrorType:
        code = default_error_code(error_type)
        assert error_type_for_code(code) is error_type


def test_error_code_registry_is_finite_and_labeled():
    """子类数量、映射与默认置信度保持稳定。"""
    assert len(ErrorCode) == 18
    assert {spec.code for spec in ERROR_CODE_SPECS} == set(ErrorCode)
    for spec in ERROR_CODE_SPECS:
        assert spec.label
        assert 0 <= spec.default_confidence <= 1
        assert error_type_for_code(spec.code) is spec.error_type


def test_coerce_error_code_accepts_known_values():
    """已知枚举与字符串原样保留。"""
    code = ErrorCode.READING_INEQUALITY_DIRECTION
    assert coerce_error_code(code, ErrorType.FORMULA) is code
    assert (
        coerce_error_code(code.value, ErrorType.FORMULA) is code
    )


def test_coerce_error_code_falls_back_for_unknown_values():
    """顶层中文、未知字符串与空值都回落到顶层默认子类。"""
    fallback = ErrorType.READING
    expected = default_error_code(fallback)
    assert coerce_error_code("概念不清", fallback) is expected
    assert coerce_error_code("unknown.code", fallback) is expected
    assert coerce_error_code(None, fallback) is expected
