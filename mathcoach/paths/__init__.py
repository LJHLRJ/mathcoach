"""多解路径：静态内容元数据、检查点判定与目录加载。

路径不是运行时生成的证明，而是由内容声明的可验证关键步骤；数学内容在
加载期通过 verify 预检，运行时用现有步骤判定。
"""
from .checker import check_checkpoint
from .catalog import (
    DEFAULT_PATH_DIR,
    PATHS,
    PathCatalog,
    PathCatalogError,
    default_verify,
    load_path_catalog,
)
from .models import PathCheckpoint, SolutionPath

__all__ = [
    "DEFAULT_PATH_DIR",
    "PATHS",
    "PathCatalog",
    "PathCatalogError",
    "PathCheckpoint",
    "SolutionPath",
    "check_checkpoint",
    "default_verify",
    "load_path_catalog",
]
