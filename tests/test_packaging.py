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
