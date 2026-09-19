# -*- coding: utf-8 -*-
"""工单 module-hwcheck/05 的**行为红证**：把产物里那一节真跑起来，看判定翻不翻 FAIL。

用法：python .scratch/module-hwcheck/probe-05-verdict-behaviour.py

## 为什么要有这一支（票面「红证 = 把探头期望值改错 → 判定翻 FAIL」）

判据强度探针（`negative-verify-05.py`）证明的是"**守卫**坏了会红"，而票面那条红证
问的是另一件事：**产物自己**的判定会不会翻。板上没法跑（本机没有 MPU6050），但
那一节的**控制流**是纯 C——可以拿宿主机编译器（本机 `C:/mingw64/bin/gcc.exe`）把
**渲染器真产出的代码**编起来跑：把探头桩函数的返回值从 0x68 改成 0x69，看它是不是
改打 FAIL、并且**不再往下打六轴读数**（`return;` 那一条）。

所以本探针不重写任何判据——它把 `render_recipe_section` 的**真输出**（库内真配方）
塞进一个桩环境里编译运行，断言的是四个**行为**：

| 形态 | 桩返回值 | 断言 |
|---|---|---|
| stm32 探头命中 | `MPU6050_Read()` → 0x68 | 打「通信探头：OK」+ 六轴读数 + 「通信正常」，**没有** FAIL |
| stm32 探头不命中 | → 0x69 | 打「通信探头：FAIL」+ 中文排查话术 + 「通信失败」，**没有**任何读数（先 return 了） |
| mspm0 两级自证都过 | `DMP_Init()`/`DMP_Read_Data()` → 0 | 打「初始化：OK」「通信探头：OK」+ 角度拆出的整数/小数 |
| mspm0 探头不命中 | `DMP_Read_Data()` → -1 | 打 FAIL + 排查话术，**没有**角度读数 |

框架那几个函数（`hwcheck_report` / `hwcheck_verdict` …）由桩提供并把内容回显出来
——它们是"输出通道"，不是本探针的被测对象（被测对象 = 渲染出的那一节的控制流）。
输出：probe-05-verdict-behaviour.txt
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.hwcheck_recipe import (  # noqa: E402
    interface_names,
    load_recipes,
    render_recipe_section,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.master_store import master_project_dir  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.treewalk import iter_project_files  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe-05-verdict-behaviour.txt"
GCC = shutil.which("gcc") or r"C:\mingw64\bin\gcc.exe"

# 框架侧桩（输出通道）：把那一节打出来的每个字都回显到 stdout，供断言。
FRAMEWORK_STUBS = r"""
#include <stdio.h>
static void hwcheck_report(const char *text) { fputs(text, stdout); }
static void hwcheck_newline(void) { fputc('\n', stdout); }
static void hwcheck_report_int(int value) { printf("%d", value); }
static void hwcheck_section(const char *title) { printf("\n== %s ==\n", title); }
static void hwcheck_detail(const char *text) { printf("  detail: %s\n", text); }
static void hwcheck_verdict(int ok, const char *trouble)
{
    printf(ok ? "  verdict: OK\n" : "  verdict: FAIL\n");
    if (!ok) { printf("  trouble: %s\n", trouble); }
}
static void hwcheck_verdict_probe_none(const char *hint) { printf("  none: %s\n", hint); }
"""

# 被调函数的桩头（按配方 include 段的头名各写一份，内容相同：让 include 能解析）。
STUB_HEADER = r"""
#ifndef HWCHECK_PROBE05_STUB_H
#define HWCHECK_PROBE05_STUB_H
#include <stdint.h>
extern int16_t ax, ay, az, gx, gy, gz;
void I2C_Init(void);
void MPU6050_Init(void);
void MPU6050_GetData(void);
uint8_t MPU6050_Read(uint8_t addr);
#define WHO_AM_I 0x75
int DMP_Init(void);
int DMP_Read_Data(float *pitch, float *roll, float *yaw);
#endif
"""

# 桩实现：探头返回值与角度由编译期宏控制（`-DPROBE_VALUE=0x69` 那一跑就是红证）。
STUB_IMPL = r"""
#include "stub.h"
#include <string.h>
int16_t ax, ay, az, gx, gy, gz;
void I2C_Init(void) { }
void MPU6050_Init(void) { }
void MPU6050_GetData(void)
{
    ax = 100; ay = -200; az = 16000; gx = 1; gy = 2; gz = 3;
}
uint8_t MPU6050_Read(uint8_t addr)
{
    (void)addr;
    return (uint8_t)PROBE_VALUE;
}
int DMP_Init(void) { return INIT_RC; }
int DMP_Read_Data(float *pitch, float *roll, float *yaw)
{
    *pitch = 12.34f; *roll = -5.67f; *yaw = 0.5f;
    return PROBE_RC;
}
"""


def _sections() -> dict[str, object]:
    """真库真配方 → 两个平台的小节（判据读真数据，不手写替身）。"""
    modules = REPO / "library" / "modules"
    manifests = list_modules(modules)
    interfaces = {}
    for name in (PLATFORM_STM32, PLATFORM_MSPM0):
        master = master_project_dir(REPO / "library" / "masters", name)
        headers = [] if not master.is_dir() else [
            (path.relative_to(master).as_posix(),
             path.read_text(encoding="utf-8", errors="replace"))
            for path in iter_project_files(master, pattern="*.h")
        ]
        interfaces[name] = interface_names(manifests, modules, name, headers)
    recipes = load_recipes(modules, manifests, interfaces)
    return {
        name: recipes["ml_mpu6050"].for_platform(name)
        for name in (PLATFORM_STM32, PLATFORM_MSPM0)
    }


def _build_and_run(section, *, defines: dict[str, str], workdir: Path) -> str:
    """把**渲染器真产出的那一节**编起来跑一遍，返回它的输出（UTF-8 解码）。

    产物里的 `include` 走配方自己声明的头名（工单 05 的 include 段）——这里把
    每个头名都写成同一份桩头，于是"配方要的头解析得到"这件事本身也被跑到了。
    """
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "stub.h").write_text(STUB_HEADER, encoding="utf-8")
    (workdir / "stub.c").write_text(STUB_IMPL, encoding="utf-8")
    for header in section.include:
        (workdir / header).write_text(
            '#include "stub.h"\n', encoding="utf-8")
    includes = "".join(f'#include "{header}"\n' for header in section.include)
    body = "\n".join(render_recipe_section(section))
    harness = (
        FRAMEWORK_STUBS
        + includes
        + "\nstatic void hwcheck_check_section(void)\n{\n"
        + body
        + "\n}\n\nint main(void)\n{\n    hwcheck_check_section();\n"
        + '    printf("\\n--END--\\n");\n    return 0;\n}\n'
    )
    source = workdir / "harness.c"
    source.write_text(harness, encoding="utf-8")
    exe = workdir / "harness.exe"
    flags = [f"-D{key}={value}" for key, value in defines.items()]
    build = subprocess.run(
        [GCC, "-std=c99", "-w", *flags, "-I", str(workdir), str(source),
         str(workdir / "stub.c"), "-o", str(exe)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if build.returncode != 0:
        raise RuntimeError(f"gcc 编译失败：\n{build.stdout}\n{build.stderr}")
    run = subprocess.run([str(exe)], capture_output=True)
    return run.stdout.decode("utf-8", "replace")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    lines: list[str] = [
        "# 工单 module-hwcheck/05 行为红证（把产物那一节真编真跑）", "",
        f"主机编译器：{GCC}（测的是**渲染器真产出**的那一节，不是替身）", "",
    ]
    if not Path(GCC).exists() and shutil.which("gcc") is None:
        lines.append("**没探测到主机 C 编译器**：本探针跑不了（如实标注，不假装）。")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1
    root = Path(tempfile.mkdtemp(prefix="firstep-probe05b-"))
    failures = 0
    runs: list[tuple[str, str, dict[str, str], list[tuple[str, bool]]]] = []
    sections = _sections()
    stm32 = sections[PLATFORM_STM32]
    mspm0 = sections[PLATFORM_MSPM0]
    runs = [
        ("stm32 探头命中（读回 0x68）", PLATFORM_STM32,
         {"PROBE_VALUE": "0x68", "INIT_RC": "0", "PROBE_RC": "0"},
         [("通信探头：OK", True), ("verdict: OK", True), ("ax = ", True),
          ("gz = ", True), ("ax = 100", True), ("gz = 3", True),
          ("verdict: FAIL", False), ("FAIL", False), ("通信失败", False)]),
        ("stm32 探头不命中（读回 0x69）", PLATFORM_STM32,
         {"PROBE_VALUE": "0x69", "INIT_RC": "0", "PROBE_RC": "0"},
         [("通信探头：FAIL", True), ("verdict: FAIL", True),
          ("通信失败：先查供电 / 上拉 / 地址 / 线序", True),
          ("ax = ", False), ("gz = ", False), ("通信正常", False)]),
        ("mspm0 两级自证都过", PLATFORM_MSPM0,
         {"PROBE_VALUE": "0", "INIT_RC": "0", "PROBE_RC": "0"},
         [("初始化：OK", True), ("通信探头：OK", True),
          ("(int)pitch = 12", True), ("= 3 ", True), ("= -5 ", True),
          ("= -6 ", True), ("= 0 ", True), ("= 5 ", True),
          ("verdict: FAIL", False)]),
        ("mspm0 探头不命中", PLATFORM_MSPM0,
         {"PROBE_VALUE": "0", "INIT_RC": "0", "PROBE_RC": "-1"},
         [("通信探头：FAIL", True), ("verdict: FAIL", True),
          ("(int)pitch", False), ("= -5 ", False)]),
    ]
    try:
        for label, platform, defines, checks in runs:
            section = sections[platform]
            try:
                transcript = _build_and_run(
                    section, defines=defines,
                    workdir=root / f"{platform}-{abs(hash(label)) % 10000}")
            except Exception as exc:  # noqa: BLE001 —— 证据脚本要结论不要栈
                lines.append(f"## {label}：编译 / 运行失败 —— {exc}")
                failures += 1
                continue
            bad: list[str] = []
            for needle, expected in checks:
                present = needle in transcript
                if present != expected:
                    bad.append(f"{'应出现' if expected else '不该出现'}「{needle}」")
            lines.append(f"## {label}：{'PASS' if not bad else 'FAIL'}"
                         + ("" if not bad else " —— " + "；".join(bad)))
            if bad:
                failures += 1
            # 原始转录（换行归一，方便人眼比对）
            lines.append("```")
            lines.extend(transcript.strip("\n").splitlines()[:24])
            lines.append("```")
            lines.append("")
        lines.append("## 结论")
        lines.append(
            f"{len(runs)} 次真跑，{len(runs) - failures} 次符合预期、{failures} 次不符。"
            + ("票面那条红证成立：探头值从 0x68 改成 0x69，判定翻 FAIL 且不再打读数。"
               if not failures else "**有形态不符**。")
        )
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1 if failures else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
