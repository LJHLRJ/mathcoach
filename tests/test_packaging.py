"""打包配置回归：安装包必须包含应用入口与知识卡片。"""
import importlib.util
import tomllib
from pathlib import Path

import mathcoach

ROOT = Path(__file__).resolve().parents[1]


def test_build_config_includes_app_and_content():
    """构建配置包含应用入口与内容包。"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'py-modules = ["app"]' in pyproject
    assert '"content*"' in pyproject
    assert "[tool.setuptools.package-data]" in pyproject
    assert 'mathcoach = "mathcoach.launcher:main"' in pyproject


def test_build_config_includes_learning_cards_and_static_assets():
    """构建配置包含学习卡与静态资源。"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"learning_cards/*.md"' in pyproject
    assert '"static*"' in pyproject
    assert '"static" = ["overlay/*"]' in pyproject
    assert (ROOT / "static" / "overlay" / "confetti.html").is_file()


def test_build_config_includes_kc_definitions():
    """构建配置包含 content/kc 教学定义。"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"kc/*.yaml"' in pyproject
    assert (ROOT / "content" / "kc" / "hs-trig-002.yaml").is_file()


def test_build_config_includes_board_and_scenario_content():
    """构建配置包含分步板书与情境仿真内容。"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"board/*.yaml"' in pyproject
    assert '"scenario/*.yaml"' in pyproject
    assert (ROOT / "content" / "board" / "hs-trig-004-e1.yaml").is_file()
    assert (ROOT / "content" / "scenario" / "hs-func-004.yaml").is_file()


def test_build_config_includes_solution_paths():
    """构建配置包含多解路径内容。"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"paths/*.yaml"' in pyproject
    assert (ROOT / "content" / "paths" / "hs-trig-002-e2.yaml").is_file()


def test_app_module_is_discoverable():
    """app 模块可被导入系统发现。"""
    spec = importlib.util.find_spec("app")
    assert spec is not None
    assert spec.origin == str(ROOT / "app.py")


def test_content_is_an_importable_package():
    """content 目录可作为包导入。"""
    import content

    assert Path(content.__file__).name == "__init__.py"


def test_version_matches_pyproject():
    """包版本与 pyproject 声明一致。"""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert mathcoach.__version__ == data["project"]["version"]


def test_runtime_dependencies_include_plotly():
    """运行依赖包含 plotly。"""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]

    assert any(dependency.startswith("plotly") for dependency in dependencies)


def test_package_declares_license_file():
    """项目声明 Apache-2.0 并携带 LICENSE。"""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    project = data["project"]
    assert project["license"] == "Apache-2.0"
    assert "LICENSE" in project["license-files"]
    assert (ROOT / "LICENSE").is_file()
