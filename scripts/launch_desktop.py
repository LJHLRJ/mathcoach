"""MathCoach 桌面启动器：本地 Streamlit 子进程 + PyWebview 原生窗口。

源码运行：python scripts/launch_desktop.py
打包运行：PyInstaller 以本文件为入口，app.py 与 content/ 作为数据文件随包分发。
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_TITLE = "数学陪练"
HEALTH_PATH = "/_stcore/health"
HEALTH_TIMEOUT_S = 40.0
SERVER_FLAG = "--streamlit-server"


def bundle_root() -> Path:
    """资源根目录：PyInstaller 下为 sys._MEIPASS，源码下为仓库根目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[1]


def app_script() -> Path:
    return bundle_root() / "app.py"


def free_port() -> int:
    """向系统申请一个空闲端口，避免与用户已有 Streamlit 冲突。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def streamlit_argv(port: int) -> list[str]:
    return [
        "streamlit",
        "run",
        str(app_script()),
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]


def run_streamlit_server(port: int) -> None:
    from streamlit.web import cli as stcli

    sys.argv = streamlit_argv(port)
    raise SystemExit(stcli.main())


def server_command(port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        # 打包后重新调用自身，进入 --streamlit-server 分支
        return [sys.executable, SERVER_FLAG, str(port)]
    return [sys.executable, str(Path(__file__).resolve()), SERVER_FLAG, str(port)]


def wait_for_health(port: int, process: subprocess.Popen) -> None:
    """轮询 Streamlit 健康检查，避免窗口先于服务打开导致白屏。"""
    url = f"http://127.0.0.1:{port}{HEALTH_PATH}"
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "Streamlit 服务提前退出；请用 --console 重新构建以查看日志"
            )
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.25)
    raise TimeoutError(f"Streamlit 服务启动超时（{HEALTH_TIMEOUT_S:.0f} 秒）")


def run_window(port: int) -> None:
    import webview  # 延迟导入，缺少依赖时能给出可读提示

    webview.create_window(
        APP_TITLE,
        f"http://127.0.0.1:{port}",
        width=1280,
        height=860,
    )
    webview.start()


def main() -> int:
    if SERVER_FLAG in sys.argv:
        index = sys.argv.index(SERVER_FLAG)
        run_streamlit_server(int(sys.argv[index + 1]))
        return 0

    if not app_script().exists():
        print(f"未找到 app.py：{app_script()}", file=sys.stderr)
        return 2

    try:
        import webview  # noqa: F401
    except ImportError:
        print(
            "缺少 pywebview，请先手动执行："
            "python -m pip install -r requirements-packaging.txt",
            file=sys.stderr,
        )
        return 2

    port = free_port()
    process = subprocess.Popen(server_command(port))
    try:
        wait_for_health(port, process)
        run_window(port)
    finally:
        # 关闭窗口后必须回收子进程，避免残留本地服务
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
