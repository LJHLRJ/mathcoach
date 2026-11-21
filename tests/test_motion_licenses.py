"""动效资源清单、许可证与免责声明。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
README = ROOT / "README.md"


def test_motion_resources_are_documented():
    text = NOTICES.read_text(encoding="utf-8")

    for name in (
        "Radiant",
        "canvas-confetti",
        "css-doodle",
        "streamlit-animate",
        "weft-ui",
        "matanim",
        "handanim",
    ):
        assert name in text

    assert "MIT License" in text
    assert "ISC License" in text
    assert "Copyright (c) 2025 Paul Bakaus" in text
    assert "Copyright (c) 2020, Kiril Vatev" in text
    assert "未提取任何 CSS 或代码" in text
    assert "未集成，待人工核实" in text


def test_motion_disclaimer_is_verbatim():
    required = (
        "本项目的动态背景、庆祝动效与微交互参考了第三方开源资源",
        "不对第三方资源的版权状态作任何法律保证",
        "MIT / ISC / CC0 / 公有领域资源",
        "来源不明或许可证不清的资源：一律不集成",
        "不对特定设备上的帧率或耗电作保证",
    )
    notices = NOTICES.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    for phrase in required:
        assert phrase in notices
        assert phrase in readme


def test_readme_links_motion_notices():
    readme = README.read_text(encoding="utf-8")

    assert "## 动效与第三方资源" in readme
    assert "[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)" in readme


def test_canvas_confetti_license_file_exists():
    license_text = (
        ROOT
        / "static"
        / "overlay"
        / "canvas-confetti.LICENSE.txt"
    ).read_text(encoding="utf-8")

    assert "ISC License" in license_text
    assert "Copyright (c) 2020, Kiril Vatev" in license_text


def test_settings_about_shows_motion_resources_and_disclaimer(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "motion-about.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    markdown = " ".join(item.value for item in at.markdown)
    assert "Radiant" in markdown
    assert "canvas-confetti" in markdown
    assert "本项目的动态背景、庆祝动效与微交互" in markdown
