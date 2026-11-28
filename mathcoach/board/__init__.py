"""分步板书：只读帧数据、verify 预检与图形渲染。"""
from .catalog import (
    BOARD_FRAMES,
    CATALOG,
    DEFAULT_BOARD_DIR,
    BoardCatalogError,
    load_board_catalog,
)
from .models import BoardCatalog, BoardFrameSpec, frame_for, frames_for
from .render import build_frame_figure, render_frame

__all__ = [
    "BOARD_FRAMES",
    "CATALOG",
    "DEFAULT_BOARD_DIR",
    "BoardCatalog",
    "BoardCatalogError",
    "BoardFrameSpec",
    "build_frame_figure",
    "frame_for",
    "frames_for",
    "load_board_catalog",
    "render_frame",
]
