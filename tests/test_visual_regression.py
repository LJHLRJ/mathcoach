"""三状态截图级视觉回归：首屏、QUIZ、收据。

本地更新基线（需要 Chrome 或已开启 CDP 的 Chrome）：
    UPDATE_VISUAL_BASELINES=1 VISUAL_BROWSER_CDP=http://127.0.0.1:9222 \
        python -m pytest tests/test_visual_regression.py -v

CI 使用 ubuntu runner 预装的 Google Chrome（channel=chrome），
依赖与浏览器由 .github/workflows/visual-regression.yml 保证。
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Generator, Sequence
from pathlib import Path

import pytest

try:
    import numpy as np
    from PIL import Image
    from playwright.sync_api import Browser, Error as PlaywrightError, Locator, Page
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    if os.getenv("VISUAL_REQUIRE_BROWSER") == "1":
        raise
    pytest.skip(f"缺少视觉回归依赖：{exc}", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
BASELINE_DIR = ROOT / "tests" / "visual" / "baselines"
ARTIFACT_DIR = ROOT / "tests" / "visual" / "artifacts"
VIEWPORT = {"width": 1440, "height": 900}
CHANNEL = os.getenv("VISUAL_BROWSER_CHANNEL", "chrome")
CDP_URL = os.getenv("VISUAL_BROWSER_CDP")
STRICT = os.getenv("VISUAL_REQUIRE_BROWSER") == "1"
PIXEL_THRESHOLD = 24
# 基线由 CI 的 headless Chrome 生成；本地 headed Chrome 只做宽松冒烟
DEFAULT_MAX_DIFF_RATIO = 0.005 if STRICT else 0.03
MAX_DIFF_RATIO = float(
    os.getenv("VISUAL_MAX_DIFF_RATIO", str(DEFAULT_MAX_DIFF_RATIO))
)
HIDE_CSS = """
[data-testid="stStatusWidget"],
[data-testid="stToolbar"],
[data-testid="stAppDeployButton"],
#MainMenu,
footer {
  visibility: hidden !important;
}
html, body, [data-testid="stMain"], [data-testid="stSidebar"] {
  scrollbar-width: none !important;
}
*::-webkit-scrollbar {
  width: 0 !important;
  height: 0 !important;
}
*, *::before, *::after {
  transition: none !important;
  animation: none !important;
}
"""


def _free_port() -> int:
    """获取本地空闲端口。"""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_healthy(url: str, process: subprocess.Popen, log_path: Path) -> None:
    """轮询健康检查直到服务就绪。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log = log_path.read_text(encoding="utf-8", errors="replace")
            pytest.fail(f"Streamlit 提前退出：\n{log[-3000:]}")
        try:
            with opener.open(f"{url}/_stcore/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    log = log_path.read_text(encoding="utf-8", errors="replace")
    pytest.fail(f"Streamlit 60 秒内未就绪：\n{log[-3000:]}")


@pytest.fixture(scope="module")
def app_url(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    """启动 Streamlit 子进程并提供地址。"""
    port = _free_port()
    log_path = tmp_path_factory.mktemp("visual") / "streamlit.log"
    db_path = tmp_path_factory.mktemp("visual-db") / "visual.sqlite3"
    env = os.environ.copy()
    env["MATHCOACH_DB"] = str(db_path)
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_BASE_URL", None)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(APP_PATH),
                "--server.headless",
                "true",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(port),
                "--server.fileWatcherType",
                "none",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    url = f"http://127.0.0.1:{port}"
    try:
        _wait_healthy(url, process, log_path)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope="module")
def browser() -> Generator[Browser, None, None]:
    """连接或启动 Playwright 浏览器。"""
    with sync_playwright() as playwright:
        if CDP_URL:
            browser = playwright.chromium.connect_over_cdp(CDP_URL)
            remote = True
        else:
            try:
                browser = playwright.chromium.launch(
                    channel=CHANNEL, headless=True
                )
            except PlaywrightError as exc:
                message = str(exc)
                if os.getenv("VISUAL_REQUIRE_BROWSER") == "1":
                    raise
                if "not found" in message.lower() or "doesn't exist" in message:
                    pytest.skip(f"未找到可用 Chrome（channel={CHANNEL}）：{message}")
                raise
            remote = False
        try:
            yield browser
        finally:
            if not remote:
                browser.close()


@pytest.fixture()
def page(browser: Browser, app_url: str) -> Generator[Page, None, None]:
    """打开页面并注入隐藏滚动条样式。"""
    context = browser.new_context(
        viewport=VIEWPORT,
        device_scale_factor=1,
        locale="zh-CN",
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = context.new_page()
    page.set_default_timeout(30000)
    page.goto(app_url, wait_until="load", timeout=60000)
    page.add_style_tag(content=HIDE_CSS)
    page.get_by_text("目标确认 · 度量空间").wait_for()
    page.mouse.move(4, 4)
    try:
        yield page
    finally:
        context.close()


def _capture(page: Page, name: str, mask: Sequence[Locator] | None = None) -> Path:
    """截图并保存到产物目录。"""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    page.evaluate(
        "document.querySelector('[data-testid=\"stMain\"]')?.scrollTo(0, 0)"
    )
    page.evaluate("document.fonts.ready.then(() => true)")
    page.wait_for_timeout(500)
    page.mouse.move(4, 4)
    path = ARTIFACT_DIR / f"{name}.png"
    page.screenshot(
        path=str(path),
        animations="disabled",
        caret="hide",
        mask=mask or [],
        mask_color="#FF00FF",
    )
    return path


def _compare(name: str, actual_path: Path) -> str | None:
    """比较截图与基线并返回差异说明。"""
    baseline_path = BASELINE_DIR / f"{name}.png"
    if not baseline_path.is_file():
        return (
            f"{name}: 缺少基线 {baseline_path}；"
            "请用 UPDATE_VISUAL_BASELINES=1 生成并提交"
        )
    actual_img = Image.open(actual_path).convert("RGB")
    baseline_img = Image.open(baseline_path).convert("RGB")
    if actual_img.size != baseline_img.size:
        return (
            f"{name}: 尺寸不一致 actual={actual_img.size} "
            f"baseline={baseline_img.size}"
        )
    actual = np.asarray(actual_img, dtype=np.int16)
    baseline = np.asarray(baseline_img, dtype=np.int16)
    delta = np.abs(actual - baseline).max(axis=2)
    changed = delta > PIXEL_THRESHOLD
    ratio = float(changed.mean())
    if ratio <= MAX_DIFF_RATIO:
        return None
    diff_path = ARTIFACT_DIR / f"{name}.diff.png"
    overlay = actual.astype(np.uint8).copy()
    overlay[changed] = (255, 0, 0)
    Image.fromarray(overlay).save(diff_path)
    return (
        f"{name}: 差异 {ratio:.3%} 超过阈值 {MAX_DIFF_RATIO:.3%}；"
        f"实际图 {actual_path}，差异图 {diff_path}"
    )


def test_visual_states_first_screen_quiz_receipt(page):
    """三状态截图与基线比对。"""
    update = os.getenv("UPDATE_VISUAL_BASELINES") == "1"
    screenshots: list[tuple[str, Path]] = []

    screenshots.append(("first_screen", _capture(page, "first_screen")))

    page.get_by_label("今天想练到什么？").fill("搞懂度量空间")
    page.get_by_role("button", name=re.compile("确认目标")).click()
    page.get_by_text("讲解 · 度量空间").wait_for()
    page.get_by_role("button", name=re.compile("开始小测")).click()
    page.get_by_text("小测 · 第 1 / 3 题").wait_for()
    screenshots.append(("quiz", _capture(page, "quiz")))

    page.get_by_role("radio", name="三角不等式").check()
    page.get_by_role("button", name=re.compile("提交答案")).click()
    page.get_by_text("收据已生成").wait_for()
    duration_metric = page.locator('[data-testid="stMetric"]').filter(
        has_text="用时"
    )
    assert duration_metric.count() == 1
    screenshots.append(
        ("receipt", _capture(page, "receipt", mask=[duration_metric]))
    )

    if update:
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        for name, actual_path in screenshots:
            Image.open(actual_path).save(BASELINE_DIR / f"{name}.png")
        return

    failures = [
        failure
        for name, path in screenshots
        if (failure := _compare(name, path)) is not None
    ]
    assert not failures, "\n".join(failures)
