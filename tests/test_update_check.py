"""更新检查：版本号解析、比较与 GitHub Release 拉取。"""
import urllib.error
from typing import NoReturn

import pytest

from mathcoach.update_check import (
    ReleaseInfo,
    UpdateCheckError,
    check_for_update,
    is_newer,
    parse_version,
)

OFFICIAL_URL = "https://github.com/LJHLRJ/mathcoach/releases/tag/v0.3.0"


def test_parse_version_strips_v_prefix():
    """解析版本号时去掉 v 前缀。"""
    assert parse_version("v0.3.0") == (0, 3, 0)
    assert parse_version("0.2.3") == (0, 2, 3)


def test_parse_version_rejects_non_numeric():
    """非纯数字版本返回空元组。"""
    assert parse_version("bad") == ()
    assert parse_version("0.3.0-rc1") == ()


def test_is_newer_compares_numeric_parts():
    """按数字段比较版本，缺失段补零。"""
    assert is_newer("v0.3.0", "0.2.3")
    assert is_newer("0.3", "0.2.9")  # 缺失段按 0 补齐
    assert not is_newer("0.2.3", "0.2.3")
    assert not is_newer("0.2.2", "0.2.3")
    assert not is_newer("bad", "0.2.3")


def _payload(tag: str = "v0.3.0") -> dict[str, object]:
    """构造 GitHub Release 响应样例。"""
    return {"tag_name": tag, "html_url": OFFICIAL_URL, "body": "notes"}


def test_check_for_update_returns_newer_release():
    """远端版本更高时返回发布信息。"""
    info = check_for_update(
        "0.2.3", fetcher=lambda url, timeout: _payload()
    )
    assert info == ReleaseInfo(
        version="0.3.0", page_url=OFFICIAL_URL, notes="notes"
    )


def test_check_for_update_returns_none_for_same_version():
    """版本相同时不提示更新。"""
    assert check_for_update("0.3.0", fetcher=lambda url, timeout: _payload()) is None


def test_check_for_update_rejects_malformed_payload():
    """缺少字段的响应抛出更新检查错误。"""
    with pytest.raises(UpdateCheckError):
        check_for_update(
            "0.2.3", fetcher=lambda url, timeout: {"tag_name": "v0.3.0"}
        )


def test_check_for_update_wraps_network_error():
    """网络错误统一包装为更新检查错误。"""
    def fetcher(url: str, timeout: float) -> NoReturn:
        """抛出离线网络错误。"""
        raise urllib.error.URLError("offline")

    with pytest.raises(UpdateCheckError):
        check_for_update("0.2.3", fetcher=fetcher)


def test_check_for_update_rejects_unknown_release_url():
    """非官方发布地址被拒绝。"""
    payload = _payload()
    payload["html_url"] = "https://example.com/download"

    with pytest.raises(UpdateCheckError):
        check_for_update("0.2.3", fetcher=lambda url, timeout: payload)


def test_check_for_update_rejects_invalid_current_version():
    """当前版本非法时抛出更新检查错误。"""
    with pytest.raises(UpdateCheckError):
        check_for_update("bad", fetcher=lambda url, timeout: _payload())
