"""更新检查：版本号解析与比较。"""
from mathcoach.update_check import is_newer, parse_version


def test_parse_version_strips_v_prefix():
    assert parse_version("v0.3.0") == (0, 3, 0)
    assert parse_version("0.2.3") == (0, 2, 3)


def test_parse_version_rejects_non_numeric():
    assert parse_version("bad") == ()
    assert parse_version("0.3.0-rc1") == ()


def test_is_newer_compares_numeric_parts():
    assert is_newer("v0.3.0", "0.2.3")
    assert is_newer("0.3", "0.2.9")  # 缺失段按 0 补齐
    assert not is_newer("0.2.3", "0.2.3")
    assert not is_newer("0.2.2", "0.2.3")
    assert not is_newer("bad", "0.2.3")
