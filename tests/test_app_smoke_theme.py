"""M17 主题冒烟：AppTest 首屏 + config.toml 静态键检查。"""
import ast
import tomllib
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
CONFIG_PATH = ROOT / ".streamlit/config.toml"
ICONS_PATH = ROOT / "mathcoach" / "ui" / "icons.py"


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


def test_first_screen_has_card_sidebar_and_tabs(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    assert not at.exception
    assert at.subheader[0].value.startswith("目标确认 · ")
    assert any(
        "学段" in box.label or "课程" in box.label for box in at.sidebar.selectbox
    )
    assert any(
        "当前卡片" in caption.value and "课程" in caption.value
        for caption in at.sidebar.caption
    )
    assert "当前任务" in [tab.label for tab in at.tabs]


def test_receipt_shows_three_metrics_after_full_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()
    at.button[0].click().run()  # 开始小测
    at.radio[0].set_value("y = x²")
    at.button[0].click().run()

    assert not at.exception
    assert at.subheader[0].value == "收据已生成"
    assert [metric.label for metric in at.metric] == [
        "用时",
        "最高提示层级",
        "独立程度",
    ]


def _start_quiz(at) -> None:
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()
    at.button[0].click().run()  # 开始小测


def test_quiz_phase_shows_progress_between_zero_and_one(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    _start_quiz(at)

    assert not at.exception
    progress = at.get("progress")
    assert progress
    # AppTest 的 proto 用 0—100 表示百分比
    assert 0.0 <= progress[0].proto.value / 100 <= 1.0


def test_correct_answer_shows_success_feedback(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    _start_quiz(at)
    at.radio[0].set_value("y = x²")
    at.button[0].click().run()

    assert not at.exception
    assert any("答对了" in element.value for element in at.success)


def test_wrong_answer_shows_error_feedback(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    _start_quiz(at)
    at.radio[0].set_value("y² = x")
    at.button[0].click().run()

    assert not at.exception
    assert any("再看一眼提示" in element.value for element in at.error)


def test_icon_constants_use_material_syntax():
    tree = ast.parse(ICONS_PATH.read_text(encoding="utf-8"))
    constants = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id.startswith("ICON_")
        and isinstance(node.value, ast.Constant)
    }

    assert constants
    for name, value in constants.items():
        assert value.startswith(":material/"), name
        assert value.endswith(":"), name


def test_first_screen_buttons_use_material_icons(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    assert not at.exception
    assert any(
        "material" in (getattr(button, "icon", "") or "")
        for button in at.button
    )
