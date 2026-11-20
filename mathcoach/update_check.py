"""GitHub Release 更新检查：版本比较与只读查询。"""
from dataclasses import dataclass

LATEST_RELEASE_URL = "https://api.github.com/repos/LJHLRJ/mathcoach/releases/latest"
DEFAULT_TIMEOUT_S = 3.0


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
