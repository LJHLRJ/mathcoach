"""配置读取必须只依赖环境变量，默认非严格模式。"""
from mathcoach.config import content_strict


def test_content_strict_defaults_false(monkeypatch):
    monkeypatch.delenv("MATHCOACH_CONTENT_STRICT", raising=False)
    assert content_strict() is False


def test_content_strict_reads_env(monkeypatch):
    monkeypatch.setenv("MATHCOACH_CONTENT_STRICT", "1")
    assert content_strict() is True
