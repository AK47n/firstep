# -*- coding: utf-8 -*-
"""工单 02 的量具之二：**眼下到底有多少组合撞在墙上**（裁决表的概率依据）。

票面点的是 `OLED 通道 + 一件 I2C 器件`（显示件 × 传感器），但重名组的定义是
`$name` 全局唯一——若判据是全局的，那么**两件 I2C 传感器同选**（温湿度 + 光照这种
环境站常见配）也该撞。本探针把这个猜想一次性量掉，免得裁决表建立在一个没测过的
猜想上。

走产品那条路：`resolve_selection` → `auto_assign_bindings`（解同脚）→
`generate_project`；只报"生成 200 / 400（重名）/ 400（别的）"。不编译——
编译那一格由工单 02 的编译矩阵负责。

用法：`python .scratch/hwcheck-acceptance/probe-02-combos.py [--out FILE]`
先落盘再打印（本机控制台 GBK）。产物落 `tmp-matrix/`（gitignore）。
"""
import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.boards import board_for_platform  # noqa: E402
from contest_generator.compile_runner import find_ccs_tools  # noqa: E402
from contest_generator.generator import generate_project  # noqa: E402
from contest_generator.pin_bindings import auto_assign_bindings  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
BASE = REPO / ".scratch" / "hwcheck-acceptance" / "tmp-matrix" / "combos"

MAIN_C = (
    '#include "ti_msp_dl_config.h"\n'
    "int main(void)\n"
    "{\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# (标签, 选中的 slug 元组)——`led/delay/debug_uart` 是"一个能跑的骨架"，
# 让每格都代表一次真实的"上板自检"动作。
COMBOS: list[tuple[str, tuple[str, ...]]] = [
    ("骨架（只有通道）", ("led", "delay", "debug_uart")),
    ("oled＋aht10", ("led", "delay", "debug_uart", "oled", "aht10")),
    ("aht10＋bh1750（环境站）", ("led", "delay", "debug_uart", "aht10", "bh1750")),
    ("aht10＋sht30（同族互替）", ("led", "delay", "debug_uart", "aht10", "sht30")),
    ("oled＋lcd（两块屏）", ("led", "delay", "debug_uart", "oled", "lcd")),
    ("mpu6050＋aht10（硬 I2C＋软 I2C）", ("led", "delay", "debug_uart", "ml_mpu6050", "aht10")),
    ("led_beep＋gp2y1014au", ("led_beep", "gp2y1014au")),
    ("rc522＋nrf24l01", ("rc522", "nrf24l01")),
    ("dht11＋ds18b20", ("dht11", "ds18b20")),
    ("jq8900＋syn6288（两路语音）", ("jq8900", "syn6288")),
    ("hx711＋rc522", ("hx711", "rc522")),
    ("relay＋human_ir", ("relay", "human_ir")),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8，先落盘再打印）")
    args = parser.parse_args()

    lines: list[str] = []
    blocked = 0
    opened = 0
    for label, slugs in COMBOS:
        manifests = resolve_selection(MODULES, PLATFORM_MSPM0, list(slugs)).manifests
        solved = auto_assign_bindings(
            manifests, PLATFORM_MSPM0, board_for_platform(PLATFORM_MSPM0), {},
            resolve_default_conflicts=True,
        )
        out = BASE / label.replace("＋", "+").replace("（", "(").replace("）", ")")
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        try:
            generate_project(
                platform=PLATFORM_MSPM0, slugs=list(slugs), main_c_content=MAIN_C,
                output_dir=out, module_library_dir=MODULES, masters_dir=MASTERS,
                ccs_tools=find_ccs_tools(), bindings=solved.bindings or None,
            )
        except Exception as exc:
            text = str(exc)
            kind = "重名" if "引脚符号重名" in text or "Duplicate name" in text else "其他"
            dup = [
                line.strip() for line in text.splitlines()
                if line.strip().startswith("·")
            ]
            lines.append(f"[400/{kind}] {label}")
            for line in dup[:4]:
                lines.append("          " + line[:150])
            blocked += 1
            continue
        lines.append(f"[200  ] {label}")
        opened += 1

    head = [
        "=== 工单 02 裁决依据：mspm0 眼下哪些组合撞在墙上（生成期读数）===",
        f"合计 {len(COMBOS)} 格：生成 200 = {opened} 格，生成前拦下 = {blocked} 格",
        "",
    ]
    report = "\n".join(head + lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")     # 先落盘
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
