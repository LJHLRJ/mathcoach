"""配置读取必须只依赖环境变量，默认非严格模式。"""
from mathcoach.config import content_strict


def test_content_strict_defaults_false(monkeypatch):
    """未设置环境变量时默认关闭严格内容模式。"""
    monkeypatch.delenv("MATHCOACH_CONTENT_STRICT", raising=False)
    assert content_strict() is False


def test_content_strict_reads_env(monkeypatch):
    """环境变量为 1 时开启严格内容模式。"""
    monkeypatch.setenv("MATHCOACH_CONTENT_STRICT", "1")
    assert content_strict() is True
