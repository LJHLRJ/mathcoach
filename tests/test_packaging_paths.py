"""桌面打包资源路径：源码布局与 PyInstaller 模拟布局。"""
import sys
from pathlib import Path

from mathcoach.config import resolve_content_root


def test_source_layout_uses_app_directory(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    app_file = tmp_path / "app.py"

    assert resolve_content_root(app_file) == (tmp_path / "content").resolve()


def test_pyinstaller_layout_uses_bundle_directory(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert resolve_content_root(Path("/ignored/app.py")) == bundle / "content"
