"""主题配置回归：键名、值与可回退注释。"""
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".streamlit" / "config.toml"
COLOR_KEYS = (
    "primaryColor",
    "backgroundColor",
    "secondaryBackgroundColor",
    "textColor",
    "greenColor",
    "redColor",
)


def test_theme_section_has_required_keys():
    data = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    theme = data["theme"]

    assert theme["base"] in {"light", "dark"}
    assert isinstance(theme["font"], str) and theme["font"]
    for key in COLOR_KEYS:
        value = theme[key]
        assert isinstance(value, str)
        assert value.startswith("#")
        assert len(value) == 7


def test_theme_comments_keep_original_values():
    text = CONFIG.read_text(encoding="utf-8")

    assert "# 原值（v0.7.0）" in text
    assert "primaryColor=#4F8BF9" in text
    assert "backgroundColor=#FFFFFF" in text
    assert "主题变更需重启 Streamlit 生效" in text
    assert "[server]" in text
