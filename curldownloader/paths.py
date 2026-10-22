"""定位源码运行与 PyInstaller 打包后的资源目录。"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """获取开发/打包后的资源路径。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        # 源码运行时本模块位于 curldownloader/，项目根目录是其上一级
        base = Path(__file__).resolve().parent.parent
    return base.joinpath(*parts)
