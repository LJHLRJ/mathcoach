"""已安装包的应用启动器：定位随包分发的 app.py 并交给 Streamlit。"""
from __future__ import annotations

import importlib.util
import sys


def main() -> None:
    import streamlit.web.cli as stcli

    spec = importlib.util.find_spec("app")
    if spec is None or spec.origin is None:
        raise SystemExit("未找到 app.py，请从源码运行 streamlit run app.py")
    sys.argv = ["streamlit", "run", spec.origin, *sys.argv[1:]]
    raise SystemExit(stcli.main())
