"""M17 主题冒烟：AppTest 首屏 + config.toml 静态键检查。"""
import tomllib
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
CONFIG_PATH = ROOT / ".streamlit/config.toml"


def test_app_first_screen_loads_without_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    assert not at.exception
    assert at.title[0].value == "数学陪练"


def test_theme_config_has_required_keys():
    data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    theme = data["theme"]
    assert theme["base"] == "light"
    assert theme["primaryColor"] == "#4F8BF9"
    assert theme["font"] == "sans serif"
