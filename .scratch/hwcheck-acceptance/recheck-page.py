# -*- coding: utf-8 -*-
"""硬件检测复测（2026-09-25）：**同一把尺子**再量一次页面实际内容。

为什么这样写：原核查用的是 `probe-page.py` 的五个场景，这次不另造一套读数口径——
本脚本 **import 原探针**（`probe-page.py`）复用它的 `dump()`，先原样重放五个场景，
再补上四个**原探针没覆盖、而原报告点名"必 400"**的格子（OLED 通道 + 库内 I2C 器件）。
读数落 `recheck-page.txt`（不动 `probe-page.txt`：那是 2026-09-24 的基线，留着做对照）。

跑法（仓库根）：
  $env:PYTHONIOENCODING='utf-8'
  .venv\\Scripts\\python.exe .scratch\\hwcheck-acceptance\\recheck-page.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _load_original():
    """按文件路径加载原探针（文件名带连字符，不能当模块名 import）。"""
    spec = importlib.util.spec_from_file_location("probe_page", HERE / "probe-page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_original()
dump = probe.dump

# ---- ① 原五场景原样重放（与 2026-09-24 基线逐字可比） ----
dump("场景 A：只验板子活着（一件器件都不选）", "mspm0", [])
dump("场景 B：地猛星 + MPU6050（平台不对称那一格）", "mspm0", ["ml_mpu6050"])
dump("场景 C：stm32 + MPU6050（原文说只有原始六轴）", "stm32", ["ml_mpu6050"])
dump("场景 D：地猛星 + LED + OLED + 按键", "mspm0", ["led", "oled", "key"])
dump("场景 E：未专精件（看通用降级怎么说话）", "mspm0", ["aht10"])

# ---- ② 新增：原报告 §3「OLED + 任意 I2C 器件一律 400」那几格 ----
dump("场景 F：地猛星 + OLED 通道 + aht10（原报告点名必 400）", "mspm0", ["aht10"])
dump("场景 G：地猛星 + OLED 通道 + aht10 + bh1750（环境站）", "mspm0", ["aht10", "bh1750"])
dump("场景 H：地猛星 + OLED 通道 + oled + lcd（两块屏）", "mspm0", ["oled", "lcd"])
dump("场景 I：地猛星 + OLED 通道 + ml_mpu6050（专精件）", "mspm0", ["ml_mpu6050"])
dump("场景 J：地猛星 + OLED 通道 + jy61p（pilot 件）", "mspm0", ["jy61p"])
# 关掉 OLED 通道做对照：若这一格与场景 F 读数不同，说明差异确实来自通道
dump("场景 K（对照）：地猛星 + 不勾 OLED + aht10", "mspm0", ["aht10"], oled=False)

text = probe.OUT.getvalue()
(HERE / "recheck-page.txt").write_text(text, encoding="utf-8")
print(text)
