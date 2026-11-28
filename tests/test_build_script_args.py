"""打包脚本参数：支持 --output-dir，默认仍为 dist/。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dry_run(*args: str) -> subprocess.CompletedProcess:
    """以 dry-run 模式调用桌面打包脚本。"""
    return subprocess.run(
        [sys.executable, "scripts/build_desktop.py", "--dry-run", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_build_script_supports_output_dir():
    """--output-dir 会透传为 PyInstaller 的 --distpath。"""
    result = _dry_run("--output-dir", "custom-dist")

    assert result.returncode == 0
    assert "--distpath" in result.stdout
    assert "custom-dist" in result.stdout


def test_build_script_defaults_to_dist():
    """未指定输出目录时落到仓库 dist/。"""
    result = _dry_run()

    assert result.returncode == 0
    assert "--distpath" in result.stdout
    assert str(ROOT / "dist") in result.stdout
