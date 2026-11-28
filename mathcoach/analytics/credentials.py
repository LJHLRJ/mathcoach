"""学情分析专用凭据：独立文件与环境变量，不复用教学 AI 密钥。

优先级：显式参数 > ``MATHCOACH_ANALYSIS_*`` 环境变量 > 本地文件。
本地文件默认位于 ``~/.mathcoach/analysis-secrets.local``，不进入仓库。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ENV_API_KEY = "MATHCOACH_ANALYSIS_API_KEY"
ENV_BASE_URL = "MATHCOACH_ANALYSIS_BASE_URL"
ENV_MODEL = "MATHCOACH_ANALYSIS_MODEL"

ANALYSIS_SECRETS_PATH = (
    Path.home() / ".mathcoach" / "analysis-secrets.local"
)


def analysis_secrets_path() -> Path:
    """返回分析凭据文件路径。"""
    return ANALYSIS_SECRETS_PATH


def load_analysis_credentials(
    path: Path | str | None = None,
) -> tuple[str, str, str]:
    """读取分析凭据。

    环境变量优先于文件；文件缺失或损坏时返回空字符串。

    Args:
        path: 凭据文件路径；None 使用默认路径。

    Returns:
        ``(api_key, base_url, model)``。
    """
    target = Path(path) if path is not None else analysis_secrets_path()
    file_key = ""
    file_base = ""
    file_model = ""
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            file_key = str(data.get("api_key") or "")
            file_base = str(data.get("base_url") or "")
            file_model = str(data.get("model") or "")
    return (
        os.getenv(ENV_API_KEY, "") or file_key,
        os.getenv(ENV_BASE_URL, "") or file_base,
        os.getenv(ENV_MODEL, "") or file_model,
    )


def save_analysis_credentials(
    api_key: str,
    base_url: str = "",
    model: str = "",
    path: Path | str | None = None,
) -> Path:
    """保存分析凭据；全部为空时删除文件。

    Args:
        api_key: 分析专用密钥。
        base_url: 兼容接口地址。
        model: 模型名。
        path: 凭据文件路径；None 使用默认路径。

    Returns:
        凭据文件路径。
    """
    target = Path(path) if path is not None else analysis_secrets_path()
    key = api_key.strip()
    base = base_url.strip()
    name = model.strip()
    if not key and not base and not name:
        target.unlink(missing_ok=True)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target.parent, 0o700)
    except OSError:
        pass
    target.write_text(
        json.dumps(
            {"api_key": key, "base_url": base, "model": name},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target
