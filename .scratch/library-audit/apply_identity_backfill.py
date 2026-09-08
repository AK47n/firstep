"""真器件身份字段回填（工单 identity-fields/03）：只填本次核实到出处的条目。

取源（全部可核实，零编造）：
  ① 库内同硬件已有条目（motor/stm32 的 TB6612 条目、灰度传感器条目）；
  ② 立创 wiki 模块手册原页（本次抓取 dmx 70 页 / dkx-stm32f103c8t6 77 页索引核对 +
     HEAD 200 实测）；
  ③ 本地手册原文（sources/materials/lckfb-地猛星移植手册/*.md 的「模块来源」段）。

用法：$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/apply_identity_backfill.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"

DMX = "https://wiki.lckfb.com/zh-hans/dmx/module"
DKX = "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module"

GRAYSCALE_KIT = "电子积木模拟灰度传感器（寻线 / 循迹模块，3Pin 模拟量输出——页面采购链接：天猫 id=676917570259）"
GRAYSCALE_URL = "https://detail.tmall.com/item.htm?abbucket=0&id=676917570259&ns=1&spm=a21n57.1.0.0.6a6b523c8GDuHU"
TB6612_KIT = "TB6612FNG 电机驱动模块（双 H 桥——页面采购链接：淘宝 id=616285586821）"
SERVO_KIT = "SG90/MG90S 9g 舵机（页面采购链接：天猫 id=615779197448）"
OLED_KIT = "0.96 寸 OLED 显示屏 12864（SSD1306，I2C 4Pin——页面采购链接：淘宝 id=40809409804）"
K230_KIT = "立创·庐山派 K230-CanMV 视觉开发板（K230 副控板；本仓资料 sources/materials/k230资料/立创·庐山派K230-CanMV开发板原理图.pdf）"

# slug → {platform: (kit, source_url)}；未列出的平台不动
BACKFILL: dict[str, dict[str, tuple[str, str]]] = {
    # ① 库内同硬件已有条目（零编造风险）
    "motor": {
        "mspm0": (TB6612_KIT, f"{DMX}/control/tb6612-motor-drive-module.html"),
    },
    "xunji": {
        "mspm0": (GRAYSCALE_KIT, f"{DMX}/sensor/grayscale-sensor.html"),
    },
    "pid": {
        "mspm0": (GRAYSCALE_KIT, f"{DMX}/sensor/grayscale-sensor.html"),
        "stm32": (GRAYSCALE_KIT, f"{DKX}/sensor/grayscale-sensor.html"),
    },
    # ② 立创 wiki 模块手册原页（HEAD 200 实测）
    "oled": {
        "mspm0": (OLED_KIT, f"{DMX}/screen/0-96-iic-single-screen.html"),
        "stm32": (OLED_KIT, f"{DKX}/screen/0-96-iic-single-screen.html"),
    },
    "servo": {
        "mspm0": (SERVO_KIT, f"{DMX}/control/sg90-steering-engine.html"),
    },
    "k230": {
        "mspm0": (K230_KIT, "https://wiki.lckfb.com/zh-hans/lushan-pi-k230/"),
        "stm32": (K230_KIT, "https://wiki.lckfb.com/zh-hans/lushan-pi-k230/"),
    },
}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    for slug, platforms in BACKFILL.items():
        path = MODULES / slug / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for platform, (kit, url) in platforms.items():
            entry = data["platforms"][platform]
            if entry.get("kit") == kit and entry.get("source_url") == url:
                continue
            entry["kit"] = kit
            entry["source_url"] = url
            changed = True
            print(f"{slug}/{platform}: kit ← {kit[:40]}… url ← {url}")
        if changed and not check:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    if check:
        print("--check：未写盘")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
