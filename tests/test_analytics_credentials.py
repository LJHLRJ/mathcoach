"""分析专用开关与凭据隔离。"""
import json
from pathlib import Path

from mathcoach.analytics import (
    LLMNarrator,
    TemplateNarrator,
    build_narrator,
)
from mathcoach.analytics.credentials import (
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_MODEL,
    load_analysis_credentials,
    save_analysis_credentials,
)
from mathcoach.domain.settings import AppSettings


def test_analysis_credentials_round_trip(tmp_path):
    """分析密钥、接口与模型独立往返。"""
    path = tmp_path / "analysis-secrets.local"
    save_analysis_credentials(
        "analysis-key",
        "https://analysis.example/v1",
        "analysis-model",
        path=path,
    )

    assert load_analysis_credentials(path) == (
        "analysis-key",
        "https://analysis.example/v1",
        "analysis-model",
    )
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["api_key"] == "analysis-key"


def test_analysis_credentials_empty_values_remove_file(tmp_path):
    """清空凭据时删除本地文件。"""
    path = tmp_path / "analysis-secrets.local"
    save_analysis_credentials("analysis-key", path=path)
    assert path.is_file()

    save_analysis_credentials("", path=path)
    assert not path.exists()
    assert load_analysis_credentials(path) == ("", "", "")


def test_environment_overrides_file(tmp_path, monkeypatch):
    """分析环境变量优先于文件。"""
    path = tmp_path / "analysis-secrets.local"
    save_analysis_credentials(
        "file-key", "https://file.example", "file-model", path=path
    )
    monkeypatch.setenv(ENV_API_KEY, "env-key")
    monkeypatch.setenv(ENV_BASE_URL, "https://env.example")
    monkeypatch.setenv(ENV_MODEL, "env-model")

    assert load_analysis_credentials(path) == (
        "env-key",
        "https://env.example",
        "env-model",
    )


def test_teaching_key_is_not_reused(monkeypatch):
    """教学 AI 密钥不能开启在线学情分析。"""
    monkeypatch.setenv("OPENAI_API_KEY", "teaching-key")
    monkeypatch.delenv(ENV_API_KEY, raising=False)
    monkeypatch.delenv(ENV_BASE_URL, raising=False)
    monkeypatch.delenv(ENV_MODEL, raising=False)
    monkeypatch.setattr(
        "mathcoach.analytics.narrative.load_analysis_credentials",
        lambda: ("", "", ""),
    )

    assert isinstance(build_narrator(enabled=True), TemplateNarrator)


def test_analysis_key_requires_switch(monkeypatch):
    """有分析密钥但开关关闭时仍走模板。"""
    monkeypatch.setenv(ENV_API_KEY, "analysis-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert isinstance(build_narrator(enabled=False), TemplateNarrator)


def test_analysis_key_and_switch_enable_llm(monkeypatch):
    """独立开关与独立密钥同时具备时才装配 LLM。"""
    monkeypatch.setenv(ENV_API_KEY, "analysis-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    narrator = build_narrator(enabled=True)

    assert isinstance(narrator, LLMNarrator)


def test_settings_expose_analysis_switch_only_in_advanced_mapping():
    """开关进入高级设置，不进入基础导出字段。"""
    settings = AppSettings.from_mapping(
        {"analysis_online_enabled": "true"}
    )

    assert settings.analysis_online_enabled is True
    assert "analysis_online_enabled" not in settings.to_mapping()
    assert (
        settings.to_mapping(include_advanced=True)[
            "analysis_online_enabled"
        ]
        is True
    )
