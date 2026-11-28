"""静态 iframe 资源：配置、打包、许可证与本地引用。"""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".streamlit" / "config.toml"
CONFETTI_HTML = ROOT / "static" / "overlay" / "confetti.html"
CONFETTI_JS = ROOT / "static" / "overlay" / "confetti.browser.js"
CONFETTI_LICENSE = (
    ROOT / "static" / "overlay" / "canvas-confetti.LICENSE.txt"
)


def test_static_serving_is_enabled():
    """Streamlit 静态资源服务开关处于开启状态。"""
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))

    assert config["server"]["enableStaticServing"] is True


def test_confetti_overlay_is_local_and_reduced_motion_aware():
    """彩带覆盖层只引用本地脚本，并响应减少动效偏好。"""
    html = CONFETTI_HTML.read_text(encoding="utf-8")

    assert 'src="confetti.browser.js"' in html
    assert "prefers-reduced-motion" in html
    assert "http://" not in html
    assert "https://" not in html
    assert CONFETTI_JS.is_file()
    assert CONFETTI_JS.stat().st_size > 0


def test_confetti_license_is_preserved():
    """第三方脚本的版权与许可证声明保持原样。"""
    js = CONFETTI_JS.read_text(encoding="utf-8")
    license_text = CONFETTI_LICENSE.read_text(encoding="utf-8")

    assert "canvas-confetti" in js
    assert "Kiril Vatev" in js
    assert "ISC License" in license_text
    assert "Copyright (c) 2020, Kiril Vatev" in license_text


def test_desktop_build_and_launcher_include_static_serving():
    """打包脚本携带静态目录，启动器开启静态服务。"""
    build = (ROOT / "scripts" / "build_desktop.py").read_text(
        encoding="utf-8"
    )
    launcher = (ROOT / "scripts" / "launch_desktop.py").read_text(
        encoding="utf-8"
    )

    assert "static{sep}static" in build
    assert "STREAMLIT_SERVER_ENABLE_STATIC_SERVING" in launcher
