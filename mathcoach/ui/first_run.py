"""首次启动初始化：零配置建库与可操作错误提示。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import db_path
from ..domain.models import Consent
from ..domain.settings import AppSettings
from ..memory.repository import Repository, build_repository, load_consent
from .settings import current_settings, load_settings


class FirstRunError(RuntimeError):
    """首次启动初始化失败；消息面向用户，可直接展示。"""


def _database_error(exc: BaseException, path: Path) -> str:
    """把数据目录或数据库初始化失败翻译成可操作提示。"""
    if isinstance(exc, PermissionError):
        return (
            f"无法创建数据目录：{path.parent}。"
            "请检查磁盘权限与剩余空间，或设置 MATHCOACH_DB 指向可写位置。"
        )
    if isinstance(exc, OSError):
        return (
            f"无法创建数据目录或数据库文件：{path}。"
            "请检查磁盘剩余空间与目录权限，或设置 MATHCOACH_DB 指向可写位置。"
        )
    if isinstance(exc, RuntimeError):
        return (
            f"无法初始化本地数据库：{path}。"
            "数据库版本可能高于当前应用版本；请升级 MathCoach，"
            "或备份数据后使用匹配的旧版本。"
        )
    return (
        f"无法初始化本地数据库：{path}。"
        "请确认数据库文件未被其他程序占用或损坏；"
        "必要时先备份，再删除该文件后重试。"
    )


def initialize_consent(path: Path | None = None) -> Consent:
    """读取已保存的授权；数据库不可用时抛出 FirstRunError。"""
    target = path or db_path()
    try:
        return load_consent(target)
    except (OSError, sqlite3.Error, RuntimeError) as exc:
        raise FirstRunError(_database_error(exc, target)) from exc


def initialize_settings(
    consent: Consent, path: Path | None = None
) -> AppSettings:
    """读取设置并确保 settings 表存在；失败时抛出 FirstRunError。"""
    target = path or db_path()
    try:
        if not (consent.memory or consent.mistake_book):
            return current_settings(consent)
        return AppSettings.from_mapping(load_settings(str(target)))
    except (OSError, sqlite3.Error, RuntimeError) as exc:
        raise FirstRunError(_database_error(exc, target)) from exc


def initialize_repository(
    consent: Consent, path: Path | None = None
) -> Repository:
    """创建或打开本地仓储；失败时抛出 FirstRunError。"""
    target = path or db_path()
    try:
        return build_repository(consent, target)
    except (OSError, sqlite3.Error, RuntimeError) as exc:
        raise FirstRunError(_database_error(exc, target)) from exc
