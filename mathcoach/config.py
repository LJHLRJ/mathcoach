"""集中配置：只读环境变量，不散落在业务代码里。"""
import os
from pathlib import Path


def content_strict() -> bool:
    """内容严格模式：M1—M3 默认允许未完成条目，M4 起必须在环境里设为 1。"""
    return os.getenv("MATHCOACH_CONTENT_STRICT", "0") == "1"


def db_path() -> Path:
    """SQLite 路径：默认在用户数据目录，位于仓库之外；可用 MATHCOACH_DB 覆盖。"""
    override = os.getenv("MATHCOACH_DB")
    if override:
        return Path(override)
    from platformdirs import user_data_dir

    return Path(user_data_dir("mathcoach")) / "mathcoach.sqlite3"


# 自由文本解析置信度阈值，低于该值转选择题式交互（M2 起生效）
PARSED_CONFIDENCE_THRESHOLD = 0.6
