#!/usr/bin/env python3
"""构建 MathCoach 桌面客户端；只调用 PyInstaller，不安装任何依赖。"""
from __future__ import annotations

import argparse
import importlib.util
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAME = "MathCoach"
MIN_PYTHON = (3, 11)
UNVERIFIED_PYTHON = (3, 13)


def _data_separator() -> str:
    """PyInstaller 的 --add-data 在 Windows 用分号，其他平台用冒号。"""
    return ";" if platform.system() == "Windows" else ":"


def _missing(module: str) -> bool:
    return importlib.util.find_spec(module) is None


def _print_prerequisites() -> None:
    print("缺少打包依赖。请先手动执行（脚本不会自动安装）：")
    print("  python -m pip install -r requirements.txt")
    print("  python -m pip install -r requirements-packaging.txt")


def _pyinstaller_command(name: str, onefile: bool, console: bool) -> list[str]:
    sep = _data_separator()
    extras: list[str] = []
    if onefile:
        extras.append("--onefile")
    if not console:
        extras.append("--windowed")  # 双击启动时不弹控制台窗口

    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        *extras,
        "--name",
        name,
        "--paths",
        str(ROOT),
        # Streamlit 的静态资源、子模块与版本元数据必须显式收集
        "--collect-all",
        "streamlit",
        "--copy-metadata",
        "streamlit",
        "--collect-submodules",
        "mathcoach",
        # app.py 由 Streamlit 以脚本方式执行，因此作为数据文件随包分发
        "--add-data",
        f"app.py{sep}.",
        "--add-data",
        f"content{sep}content",
        str(ROOT / "scripts" / "launch_desktop.py"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 MathCoach 桌面客户端")
    parser.add_argument("--name", default=DEFAULT_NAME, help="产物名称")
    parser.add_argument("--onefile", action="store_true", help="生成单文件产物（启动更慢）")
    parser.add_argument("--console", action="store_true", help="保留控制台，便于排查启动问题")
    parser.add_argument("--dry-run", action="store_true", help="只打印命令，不执行构建")
    args = parser.parse_args()

    if sys.version_info < MIN_PYTHON:
        print(f"需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+", file=sys.stderr)
        return 2
    if sys.version_info >= UNVERIFIED_PYTHON:
        print(
            "警告：Python 3.13+ 未在本仓库验证，建议用 Python 3.11/3.12 构建。",
            file=sys.stderr,
        )

    if not (ROOT / "app.py").exists() or not (ROOT / "content").is_dir():
        print("未找到 app.py 或 content/，请在仓库根目录运行本脚本。", file=sys.stderr)
        return 2

    if _missing("streamlit") or _missing("PyInstaller") or _missing("webview"):
        _print_prerequisites()
        return 2

    command = _pyinstaller_command(args.name, args.onefile, args.console)
    print("将执行：")
    print(" ".join(command))
    if args.dry_run:
        print("--dry-run：未执行构建。")
        return 0
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
