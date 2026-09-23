# -*- coding: utf-8 -*-
"""hwcheck-unknown-device/03 真编译探针：**自建件探测小节**在 stm32 上真编译。

证的是什么（本单的验收线）：检测页为一件库外件渲染出的探测小节（自建件 ＋
`i2c_probe` 支点 ＋ 通道模块）**能过一次真编译**，且 **0 error / 0 warning**
——"能生成"与"能编译"不是两件事（spec 判据）。

跟 `compile_matrix.py`（工单 01）的分工：那支只证"支点模块本身能编译"，
本支证**产品渲染出的 main.c**（经 `hwcheck_view` + `render_main_c` 这条真路径）
在真母版工程里能编译。所以这里不手写 main.c —— 用手写的那份就绕过了要验的东西。

覆盖三种形态 × 两种通道形态（"按需渲染"那条验收线靠这两轴交叉）：

* 形态① 只有地址（只 ping）/ ② 有寄存器无期望值（只回显）/ ③ 有寄存器 + 期望值（判 OK/FAIL）
* 通道：串口 + OLED 双通道 / **无输出通道**（这一格产物里一个自建件字样都不该有）

用法：`python .scratch/hwcheck-unknown-device/probe-03-compile-stm32.py [--out FILE]`
**先落盘再打印**（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
产物落 `.scratch/hwcheck-unknown-device/matrix/`（gitignore），日志落 `matrix-logs/`。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log,
    compile_passed,
    find_uv4,
)
from contest_generator.generator import generate  # noqa: E402
from contest_generator.hwcheck import (  # noqa: E402
    HwCheckConfig,
    render_main_c,
)
from contest_generator.hwcheck_board import hwcheck_view  # noqa: E402
from contest_generator.my_devices import (  # noqa: E402
    CustomDevice,
    my_devices_dir,
    save_device,
)
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_dependencies  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
MATRIX_DIR = REPO / ".scratch" / "hwcheck-unknown-device" / "matrix"
LOG_DIR = REPO / ".scratch" / "hwcheck-unknown-device" / "matrix-logs"
WORK_DIR = REPO / ".scratch" / "hwcheck-unknown-device" / "probe-03-data"

# 五个形态：ID / 名字 / 地址 / 寄存器 / 期望值 / 是否再搭一件库内器件
CASES = {
    "shape1-ping-only": ("mine_ping", "只有地址的库外件", 0x68, None, None, None),
    "shape2-echo": ("mine_echo", "有寄存器无期望值的库外件", 0x69, 0x75, None, None),
    "shape3-judge": ("mine_judge", "有寄存器有期望值的库外件", 0x6A, 0x75, 0x68, None),
    # 混装（评审补的一格）：库内专精件 + 自建件同趟——三个"按需渲染"开关
    # （needs_hex / needs_verdict / needs_probe_none）的交点正在这里
    "mixed-library": ("mine_mixed", "与库内件同趟的库外件", 0x6B, 0x75, 0x68, "ml_mpu6050"),
    "no-channel": ("mine_nochan", "无输出通道形态的库外件", 0x6C, 0x75, 0x68, None),
}


def build_case(name: str, *, has_output_channel: bool) -> tuple[Path, str]:
    """按真路径生成一个检测工程（返回目录与 main.c）。"""
    device_id, device_name, address, register, expect, library_slug = CASES[name]
    devices = (device_id,) if library_slug is None else (library_slug, device_id)
    config = HwCheckConfig(
        platform=PLATFORM_STM32,
        debug_uart=has_output_channel,
        oled=has_output_channel,
        devices=devices,
    )
    # 自建件先落进（临时的）数据目录——判据只读那里的数据，不玩内存特例。
    # 落点是 `my_devices_dir(data_dir)`（`<数据目录>/hwcheck_devices/`），与
    # `hwcheck_view(data_dir=…)` 读的那个目录**同一个推导**（写这儿读那儿）。
    save_device(
        my_devices_dir(WORK_DIR),
        CustomDevice(
            id=device_id, name=device_name, bus="i2c",
            address=address, register=register, expect=expect,
            notes="编译探针用的一件",
        ),
    )
    view = hwcheck_view(
        config,
        module_library_dir=MODULES,
        masters_dir=MASTERS,
        data_dir=WORK_DIR,
    )
    main_c = render_main_c(config, view.sections, view.generic, view.custom)
    by_slug = {m.slug: m for m in list_modules(MODULES)}
    # **模块集吃产品算好的那一份**（`view.generation_slugs` = 摘掉自建件 + 补
    # `i2c_probe`）。这里绝不自己 `append("i2c_probe")`：手推一份就是第二个真相源，
    # 而"产品路径到底带不带支点模块"恰恰是本单要验的事（评审抓到的正是这里）。
    manifests = resolve_dependencies(list(view.generation_slugs), by_slug)
    out = MATRIX_DIR / f"custom-{name}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    generate(
        platform=PLATFORM_STM32,
        manifests=manifests,
        module_library_dir=MODULES,
        master_project_dir=MASTERS / PLATFORM_STM32,
        output_dir=out,
        main_c_content=main_c,
    )
    return out, main_c


def count_warnings(output: str) -> list[str]:
    """告警行（**排除工具汇总行**：`0 Error(s), 0 Warning(s).` 自己就含子串）。"""
    return [
        line for line in output.splitlines()
        if "warning" in line.lower() and "warning(s)" not in line.lower()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8，先落盘再打印）")
    args = parser.parse_args()

    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    ok_all = True

    for name in CASES:
        has_channel = name != "no-channel"
        try:
            out, main_c = build_case(name, has_output_channel=has_channel)
        except Exception as exc:  # 生成期失败也算不通过，如实记录
            lines.append(f"[custom/{name}] 生成期异常：{type(exc).__name__}: {exc}")
            ok_all = False
            continue
        # 无输出通道那一格：产物里不该有自建件字样（不假装测过）
        if not has_channel:
            assert "hwcheck_custom_" not in main_c, "无通道形态不该有自建件小节"
            assert "i2c_probe" not in main_c, "无通道形态不该带支点模块"
        log = collect_build_log(PLATFORM_STM32, out, uv4=find_uv4(), timeout=600)
        ok = compile_passed(PLATFORM_STM32, log.run.exit_code)
        warnings = count_warnings(log.run.output)
        (LOG_DIR / f"custom-{name}.log").write_text(
            f"exit_code={log.run.exit_code}\ncompile_passed={ok}\n\n{log.run.output}",
            encoding="utf-8",
        )
        lines.append(
            f"[custom/{name}] exit={log.run.exit_code} passed={ok} "
            f"warnings={len(warnings)}"
        )
        for warning in warnings[:8]:
            lines.append("    " + warning.strip()[:160])
        ok_all = ok_all and ok and not warnings

    lines.append("")
    lines.append(f"=== 结果：{'全部 PASS（0 error / 0 warning）' if ok_all else '有 FAIL'} ===")
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")   # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
