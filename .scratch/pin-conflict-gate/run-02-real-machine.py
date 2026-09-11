"""真机跑 generate_check.py 的免引号包装（工单 pin-conflict-gate/02）。

PowerShell → cmd → python 三层转义会把 `--bindings` 的 JSON 引号吃掉（实测
`Unterminated string`），故把 argv 写在脚本里（唯一可靠的传参姿势）。

跑什么：真机缓存推荐（12 模块）按 `--drop` 收窄到**可解形态 motor + servo**，
再带上「一键配置」的增量绑定 → 期望 /api/generate 通过 + SysConfig/gmake 编译绿。

用法：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/pin-conflict-gate/run-02-real-machine.py
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DROPPED = "k230,coord_detect,uart,key,huidu,pid,l298n,oled,ntb_time,imu_uart"

sys.argv = [
    "generate_check.py",
    "--topics-dir", "library/topics",
    "--modules-dir", "library/modules",
    "--platform", "mspm0",
    "--reuse-recommend",
    "--drop", DROPPED,
    "--bindings", '{"servo.SERVO_PWM_C0":"PA0"}',
    "2026H",
]
runpy.run_path(str(REPO / ".scratch" / "real-run" / "generate_check.py"), run_name="__main__")
