"""GitHub Release 更新检查：版本比较与只读查询。"""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

LATEST_RELEASE_URL = "https://api.github.com/repos/LJHLRJ/mathcoach/releases/latest"
DEFAULT_TIMEOUT_S = 3.0
Fetcher = Callable[[str, float], dict[str, object]]


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    page_url: str
    notes: str


class UpdateCheckError(RuntimeError):
    """更新检查失败：网络、响应格式或版本号异常。"""


def parse_version(value: str) -> tuple[int, ...]:
    """把 v0.3.0 解析为 (0, 3, 0)；非法版本返回空元组。"""
    text = value.strip().lstrip("vV")
    parts = text.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        return ()
    return tuple(int(part) for part in parts)


def is_newer(latest: str, current: str) -> bool:
    """按数字段比较版本，缺失段补 0；任一版本非法时返回 False。"""
    latest_parts = parse_version(latest)
    current_parts = parse_version(current)
    if not latest_parts or not current_parts:
        return False
    size = max(len(latest_parts), len(current_parts))
    latest_padded = latest_parts + (0,) * (size - len(latest_parts))
    current_padded = current_parts + (0,) * (size - len(current_parts))
    return latest_padded > current_padded


def _fetch_json(url: str, timeout_s: float) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MathCoach",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            if getattr(response, "status", 200) != 200:
                raise UpdateCheckError("GitHub API 返回异常状态")
            payload = json.loads(response.read().decode("utf-8"))
    except UpdateCheckError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise UpdateCheckError("无法获取更新信息") from exc
    if not isinstance(payload, dict):
        raise UpdateCheckError("更新信息格式错误")
    return payload


def _release_from_payload(payload: object) -> ReleaseInfo:
    if not isinstance(payload, dict):
        raise UpdateCheckError("更新信息格式错误")
    tag = payload.get("tag_name")
    page_url = payload.get("html_url")
    if not isinstance(tag, str) or not isinstance(page_url, str):
        raise UpdateCheckError("更新信息格式错误")
    version = tag.strip().lstrip("vV")
    if not parse_version(version):
        raise UpdateCheckError("无法解析版本号")
    # 只接受本仓库的 Release 页面，避免把用户导向未知地址
    if not page_url.startswith("https://github.com/LJHLRJ/mathcoach/"):
        raise UpdateCheckError("下载地址不是官方仓库")
    notes = payload.get("body")
    return ReleaseInfo(
        version=version,
        page_url=page_url,
        notes=notes if isinstance(notes, str) else "",
    )


def fetch_latest_release(timeout_s: float = DEFAULT_TIMEOUT_S) -> ReleaseInfo:
    """读取 GitHub Releases latest；失败抛 UpdateCheckError。"""
    return _release_from_payload(_fetch_json(LATEST_RELEASE_URL, timeout_s))


def check_for_update(
    current_version: str,
    fetcher: Fetcher | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ReleaseInfo | None:
    """有新版本时返回 ReleaseInfo，否则返回 None；网络/格式异常抛 UpdateCheckError。"""
    if not parse_version(current_version):
        raise UpdateCheckError("当前版本号无法解析")
    if fetcher is None:
        release = fetch_latest_release(timeout_s)
    else:
        try:
            payload = fetcher(LATEST_RELEASE_URL, timeout_s)
        except UpdateCheckError:
            raise
        except Exception as exc:
            # 注入的 fetcher 可能是 urllib 或其他实现，统一转成可读错误
            raise UpdateCheckError("无法获取更新信息") from exc
        release = _release_from_payload(payload)
    return release if is_newer(release.version, current_version) else None
