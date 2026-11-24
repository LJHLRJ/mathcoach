"""打包配置回归：安装包必须包含应用入口与知识卡片。"""
import importlib.util
import tomllib
from pathlib import Path

import mathcoach

ROOT = Path(__file__).resolve().parents[1]


def test_build_config_includes_app_and_content():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'py-modules = ["app"]' in pyproject
    assert '"content*"' in pyproject
    assert "[tool.setuptools.package-data]" in pyproject
    assert 'mathcoach = "mathcoach.launcher:main"' in pyproject


def test_build_config_includes_learning_cards_and_static_assets():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"learning_cards/*.md"' in pyproject
    assert '"static*"' in pyproject
    assert '"static" = ["overlay/*"]' in pyproject
    assert (ROOT / "static" / "overlay" / "confetti.html").is_file()


def test_app_module_is_discoverable():
    spec = importlib.util.find_spec("app")
    assert spec is not None
    assert spec.origin == str(ROOT / "app.py")


def test_content_is_an_importable_package():
    import content

    assert Path(content.__file__).name == "__init__.py"


def test_version_matches_pyproject():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert mathcoach.__version__ == data["project"]["version"]


def test_runtime_dependencies_include_plotly():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]

    assert any(dependency.startswith("plotly") for dependency in dependencies)


def test_package_declares_license_file():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    project = data["project"]
    assert project["license"] == "Apache-2.0"
    assert "LICENSE" in project["license-files"]
    assert (ROOT / "LICENSE").is_file()
