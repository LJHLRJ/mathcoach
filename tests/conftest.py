"""本地测试默认启用严格内容模式；CI workflow 同样注入该值。"""
import os

os.environ.setdefault("MATHCOACH_CONTENT_STRICT", "1")
