"""沙箱专用入口（模拟用户机上的启动方式）。

为什么需要它：生产入口 `python -m contest_generator.webapp` 用的是模块级 app，
配置路径固定为 `~/.contest_generator`——沙箱要**独立数据目录**（不碰真身配置），
所以这里自己建 AppContext 再起服务。端口 8020 与沙箱启动器一致。

被更新器覆盖后本文件内容会被替换成正式版（firstep 包内没有 sim-run.py，
所以它会被保留——这正是「包内没有的文件不被删」的表现）。
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from contest_generator.webapp import AppContext, create_app

SANDBOX_DATA = Path(r"C:\Users\luoji\.contest_generator_sim")
PORT = int(os.environ.get("FIRSTEP_LAUNCHER_PORT", "8020"))

if __name__ == "__main__":
    ctx = AppContext(config_path=SANDBOX_DATA / "config.json")
    uvicorn.run(create_app(ctx), host="127.0.0.1", port=PORT)
