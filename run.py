#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VPN 工作台薄入口 —— 将 src 加入导入路径，业务逻辑由 cli 编排。

使用：
    python3 run.py --help
依赖：Python 3.8+；运行桌面认证另需系统 PyGObject/GTK3。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from vpn_workbench.cli import main

if __name__ == "__main__":
    sys.exit(main())
