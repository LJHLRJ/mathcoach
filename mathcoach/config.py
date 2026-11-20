"""集中配置：只读环境变量，不散落在业务代码里。"""
import os


def content_strict() -> bool:
    """内容严格模式：M1—M3 默认允许未完成条目，M4 起必须在环境里设为 1。"""
    return os.getenv("MATHCOACH_CONTENT_STRICT", "0") == "1"


# 自由文本解析置信度阈值，低于该值转选择题式交互（M2 起生效）
PARSED_CONFIDENCE_THRESHOLD = 0.6
