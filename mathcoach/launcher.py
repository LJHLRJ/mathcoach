"""已安装包的应用启动器：定位随包分发的 app.py 并交给 Streamlit。"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    import streamlit.web.cli as stcli

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    if not app_path.exists():
        raise SystemExit("未找到 app.py，请从源码运行 streamlit run app.py")
    sys.argv = ["streamlit", "run", str(app_path), *sys.argv[1:]]
    raise SystemExit(stcli.main())
