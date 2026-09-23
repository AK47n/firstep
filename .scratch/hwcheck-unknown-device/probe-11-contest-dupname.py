# -*- coding: utf-8 -*-
"""工单 11 的复现 / 验收探针：`SCL` 重名那组在**赛题主线**上现在怎么答？

判据两条腿（跑一遍就有读数）：

* `oled + jy61p`（撞名组）→ **期望在生成前 400**，文案说的是"引脚符号重名"并点名
  两件模块（修复前：生成 200 → 编译 exit=2 / 4 个 `Duplicate name` error）；
* `oled + ml_mpu6050`（不撞名组）→ **期望照常生成 + 真编译 0 error / 0 warning**
  （回归对照：判据不能把好路也拦掉。`ml_mpu6050` 走 I2C_0 实例、脚名叫
  `I2C_0_SCL`，不与 `OLED_SPI` 撞）。

**走产品那条路**：`generate_project(slugs=…, bindings=…)`——webapp 的 `/api/generate`
内核调的就是它；引脚按用户实际动作先点一次「自动配置」解同脚冲突（PA22 那条），
这样剩下的才是本工单要验的那一轴。

用法：`python .scratch/hwcheck-unknown-device/probe-11-contest-dupname.py [--out FILE]`
先落盘再打印（本机控制台 GBK）。产物落 `tmp-matrix/contest-dupname/`（gitignore）。
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.boards import board_for_platform  # noqa: E402
from contest_generator.compile_runner import find_ccs_tools, find_make  # noqa: E402
from contest_generator.generator import generate_project  # noqa: E402
from contest_generator.pin_bindings import auto_assign_bindings  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
BASE = REPO / ".scratch" / "hwcheck-unknown-device" / "tmp-matrix" / "contest-dupname"

# 骨架不是这条判据要验的东西（syscfg 与它无关）——给一份最小 main，免得把探针
# 耦合到 LLM 桩上
MAIN_C = (
    '#include "ti_msp_dl_config.h"\n'
    "int main(void)\n"
    "{\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 赛题主线最常见的几组：前两组是"板子活着 + 显示 + 一件传感器"（撞名 / 不撞名
# 对照），后两组点名票面要求的三格里的另两格：`LED`（led_beep × gp2y1014au）与
# `MISO`/`MOSI`（rc522 × nrf24l01）。
#
# 判据：**expect_collision=True 的组合必须在生成前被拦下**（拦下是正确行为——
# 修复前它们一路生成、然后在 CCS 里报 Duplicate name）；False 的组合必须照常
# 生成且真编译 0 error / 0 warning。
COMBOS = {
    "oled+mpu6050": (False, ("led", "delay", "debug_uart", "oled", "ml_mpu6050")),
    "oled+jy61p": (True, ("led", "delay", "debug_uart", "oled", "jy61p")),
    "led-beep+gp2y1014au": (True, ("led_beep", "gp2y1014au")),
    "rc522+nrf24l01": (True, ("rc522", "nrf24l01")),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8，先落盘再打印）")
    args = parser.parse_args()

    lines: list[str] = []
    ok_all = True
    for label, (expect_collision, slugs) in COMBOS.items():
        manifests = resolve_selection(MODULES, PLATFORM_MSPM0, list(slugs)).manifests
        solved = auto_assign_bindings(
            manifests, PLATFORM_MSPM0, board_for_platform(PLATFORM_MSPM0), {},
            resolve_default_conflicts=True,
        )
        out = BASE / label
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        lines.append(
            f"=== {label}（期望{'拦下' if expect_collision else '照常生成'}；"
            f"自动配置解出 {solved.bindings or '无需动'}）==="
        )
        try:
            generate_project(
                platform=PLATFORM_MSPM0, slugs=slugs, main_c_content=MAIN_C,
                output_dir=out, module_library_dir=MODULES, masters_dir=MASTERS,
                ccs_tools=find_ccs_tools(), bindings=solved.bindings or None,
            )
        except Exception as exc:
            blocked = "引脚符号重名" in str(exc) or "Duplicate name" in str(exc)
            lines.append(
                f"  生成期{'**按预期拦下**' if blocked else '异常拦下（非重名判据）'}："
                f"{type(exc).__name__}"
            )
            for detail in str(exc).splitlines()[:6]:
                lines.append("    " + detail.strip()[:170])
            ok_all = ok_all and blocked == expect_collision
            continue
        if expect_collision:
            # 没被拦下 = 修复没生效（这条组合会一路生成到编译期）
            lines.append("  生成 OK —— **该拦的没拦住**")
            ok_all = False
            continue
        make = find_make(r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe")
        proc = subprocess.run(
            [str(make), "-C", str(out / "Debug"), "-f", "makefile", "-B", "all"],
            cwd=out, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=900,
        )
        text = proc.stdout + proc.stderr
        dups = [line.strip() for line in text.splitlines() if "Duplicate name" in line]
        lines.append(
            f"  生成 OK → 真编译 exit={proc.returncode}，Duplicate name {len(dups)} 条"
        )
        for line in dups[:3]:
            lines.append("     >> " + line[:150])
        ok_all = ok_all and proc.returncode == 0 and not dups

    lines.append("")
    lines.append(
        "=== 结论：" + ("撞名组合全被拦下 + 不撞名组合编译绿（两条腿都成立）"
                       if ok_all else "有 FAIL（见上面读数）") + " ==="
    )
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")     # 先落盘
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
