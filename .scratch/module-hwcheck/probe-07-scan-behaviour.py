# -*- coding: utf-8 -*-
"""工单 module-hwcheck/07 的**行为证据**：把渲染出的整份 main.c 编起来真跑。

用法：python .scratch/module-hwcheck/probe-07-scan-behaviour.py

## 为什么要这一支

票面第二条验收写的是行为：「通用路径 = 初始化 +（I2C 类件）总线地址扫描；
扫描结果打印**应答地址清单 / 无应答**」。文本断言证明不了"扫描真能认出器件"，
板上又没器件（本机没有地猛星 / 最小六轴 / 软 I2C 传感器）——但那一节的时序是
纯 C：拿宿主机编译器（本机 `C:/mingw64/bin/gcc.exe`）把**渲染器真产出的整份
main.c**（工单 07 的通用小节 + 框架）编起来，给 `gpio_*` 配一个**I2C 从机仿真**
（SCL 上升沿收地址字节、第 9 拍按地址是否匹配拉低 SDA），就能在两件事上给出
行为结论：

| 形态 | 仿真里的从机 | 断言（跑出来的字） |
|---|---|---|
| sht20 总线上有器件 @0x3C | 地址匹配 | 打「应答：0x3C」、「未判定：1 项」，**没有**「无应答」 |
| sht20 总线上没有器件 | 谁都不应答 | 打「无应答」+ 供电 / 上拉 / 线序排查话术，**没有**「应答：0x」 |
| 初始化 | —— | `sht20_init()` **真被调用**（桩里打点），且**没有被读函数调用**（`sht20_read` 桩一进就 abort） |

最后一条正是"不猜读函数"的行为面：桩把 `sht20_read` 实现成 `abort()`——通用
小节只要碰了它，这一跑直接崩，红得没有歧义。

输出：probe-07-scan-behaviour.txt（每个形态的完整 stdout 也在里面）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.hwcheck import HwCheckConfig, render_main_c  # noqa: E402
from contest_generator.hwcheck_generic import (  # noqa: E402
    plan_generic_section,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe-07-scan-behaviour.txt"
GCC = shutil.which("gcc") or r"C:\mingw64\bin\gcc.exe"
LIBRARY = REPO / "library" / "modules"

# 框架 / 平台桩：进门头（真实工程里是 ml_gpio.h 那一套）、串口打印、心跳。
#
# ⚠ 这一段的 `gpio_*` **不是空桩**：它仿真一条 I2C 总线（见模块 docstring）。
# 仿真只按"SCL 上升沿采样 SDA、第 9 拍看从机拉不拉低"这一条 I2C 事实走，
# 不掺任何与被测代码耦合的假设——被测代码驱动的是真时序。
STUBS = r"""
#include "headfile.h"
#include <stdio.h>
#include <stdlib.h>

/* ---- I2C 从机仿真：SLAVE_ADDR < 0 = 这条总线上没有器件 ---- */
#define SCL_PIN Pin_6
#define SDA_PIN Pin_7

static int g_scl, g_sda_out, g_sda_input, g_bit_index, g_byte, g_ack;
static int g_starts;

void gpio_init(GPIOn_enum port, Pinx_enum pin, GPIO_MODE_enum mode)
{
    (void)port;
    if (pin == SDA_PIN) { g_sda_input = (mode == IU); }
    if (pin == SCL_PIN) { g_scl = 0; }
}

void gpio_set(GPIOn_enum port, Pinx_enum pin, uint8_t value)
{
    (void)port;
    if (pin == SDA_PIN)
    {
        int next = value ? 1 : 0;
        /* 起始位：SCL 高电平期间 SDA 由高变低 → 新一次传输，清收位计数 */
        if (g_scl && g_sda_out && !next && !g_sda_input) {
            g_bit_index = 0; g_byte = 0; g_ack = 0; g_starts++;
        }
        g_sda_out = next;
        return;
    }
    if (pin == SCL_PIN)
    {
        int next = value ? 1 : 0;
        if (next && !g_scl)                    /* SCL 上升沿 */
        {
            if (g_sda_input) {                 /* 第 9 拍：从机在这拍应答 */
                g_ack = (SLAVE_ADDR >= 0 && g_byte == (SLAVE_ADDR << 1)) ? 1 : 0;
            } else if (g_bit_index < 8) {      /* 收地址字节 */
                g_byte = (g_byte << 1) | g_sda_out;
                g_bit_index++;
            }
        }
        g_scl = next;
    }
}

uint8_t gpio_get(GPIOn_enum port, Pinx_enum pin)
{
    (void)port;
    if (pin == SDA_PIN && g_sda_input) { return g_ack ? 0 : 1; }
    return 1;                                  /* 上拉：没有从机应答就是高 */
}

void SystemInit(void) { }
void led_init(uint8_t channel) { (void)channel; }
void led_toggle(uint8_t channel) { (void)channel; }
void debug_uart_init(void) { }

static int g_loops;
void delay_ms(uint32_t ms)
{
    (void)ms;
    if (++g_loops > 2) { printf("\n--END-- (starts=%d)\n", g_starts); exit(0); }
}

const char *debug_cmd_peek(void) { return ""; }
void debug_cmd_consume(void) { }
void debug_cmd_poll(void) { }

/* ---- 被测模块（sht20）的桩：初始化打点；读函数一碰就崩 ---- */
void sht20_init(void) { printf("[STUB] sht20_init() 被调用\n"); }
int sht20_read(float *t, float *h)
{
    (void)t; (void)h;
    printf("[STUB] sht20_read() **被调用** —— 通用降级不许猜读函数！\n");
    abort();
    return 1;
}
int sht20_read_temperature(void) { abort(); return 0; }
"""

# 进门头（真机上是 ml_libs/headfile.h → ml_gpio.h）：类型与函数声明在这，
# 值（GPIO_A / Pin_6）给 pin_config.h 用——**顺序与真工程一致**（先 headfile
# 后 pin_config，这正是 main.c 里那两行 include 的次序）。
HEADFILE_STUB = r"""#ifndef HWCHECK_PROBE07_HEADFILE_H
#define HWCHECK_PROBE07_HEADFILE_H
#include <stdio.h>
#include <stdint.h>

typedef enum { GPIO_A = 0x00, GPIO_B = 0x01, GPIO_C = 0x02 } GPIOn_enum;
typedef enum { Pin_0 = 0, Pin_6 = 6, Pin_7 = 7 } Pinx_enum;
typedef enum { OUT_PP = 0x00, AF_PP = 0x03, OUT_OD = 0x02, IU = 0x01 } GPIO_MODE_enum;

void gpio_init(GPIOn_enum port, Pinx_enum pin, GPIO_MODE_enum mode);
void gpio_set(GPIOn_enum port, Pinx_enum pin, uint8_t value);
uint8_t gpio_get(GPIOn_enum port, Pinx_enum pin);
void SystemInit(void);
void led_init(uint8_t channel);
void led_toggle(uint8_t channel);
void debug_uart_init(void);
void delay_ms(uint32_t ms);
const char *debug_cmd_peek(void);
void debug_cmd_consume(void);
void debug_cmd_poll(void);
#define DEBUG_PRINTF(...) printf(__VA_ARGS__)
#endif
"""
SERIAL_STUB = '#include "headfile.h"\n'
LED_INSTANCES_STUB = "#define LED_RED 0\n"
# 工程根引脚宏（真机上是母版 pin_config.h，值 = SHT20 的默认脚 PA6/PA7）
PIN_CONFIG_STUB = (
    "#ifndef PIN_CONFIG_H\n#define PIN_CONFIG_H\n"
    "typedef int GPIOn_enum_alias;\n"
    "#define SHT20_SCL_GPIO GPIO_A\n#define SHT20_SCL_PIN  Pin_6\n"
    "#define SHT20_SDA_GPIO GPIO_A\n#define SHT20_SDA_PIN  Pin_7\n"
    "#endif\n"
)
SHT20_STUB = (
    "#ifndef SHT20_STM32_H\n#define SHT20_STM32_H\n"
    "void sht20_init(void);\n"
    "int sht20_read(float *t, float *h);\n"
    "int sht20_read_temperature(void);\n#endif\n"
)


def _generic_sections():
    manifest = next(m for m in list_modules(LIBRARY) if m.slug == "sht20")
    entry = manifest.platforms[PLATFORM_STM32]
    headers = [
        (rel, (LIBRARY / "sht20" / rel).read_text(encoding="utf-8"))
        for rel in entry.files if rel.lower().endswith(".h")
    ]
    return [plan_generic_section(PLATFORM_STM32, manifest, headers)]


def _run(*, slave_addr: int, workdir: Path) -> tuple[str, int]:
    """编译并运行**渲染器真产出的整份 main.c**，返回 (stdout, 退出码)。"""
    workdir.mkdir(parents=True, exist_ok=True)
    config = HwCheckConfig(
        platform=PLATFORM_STM32, debug_uart=True, oled=False, devices=("sht20",))
    main_c = render_main_c(config, (), _generic_sections())
    (workdir / "main.c").write_text(main_c, encoding="utf-8")
    (workdir / "headfile.h").write_text(HEADFILE_STUB, encoding="utf-8")
    (workdir / "debug_uart.h").write_text(SERIAL_STUB, encoding="utf-8")
    (workdir / "led_instances.h").write_text(LED_INSTANCES_STUB, encoding="utf-8")
    (workdir / "pin_config.h").write_text(PIN_CONFIG_STUB, encoding="utf-8")
    (workdir / "sht20_stm32.h").write_text(SHT20_STUB, encoding="utf-8")
    (workdir / "stubs.c").write_text(STUBS, encoding="utf-8")
    exe = workdir / "main.exe"
    build = subprocess.run(
        [GCC, "-std=c99", "-w", f"-DSLAVE_ADDR={slave_addr}", "-I", str(workdir),
         str(workdir / "main.c"), str(workdir / "stubs.c"), "-o", str(exe)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if build.returncode != 0:
        raise RuntimeError(f"gcc 编译失败：\n{build.stdout}\n{build.stderr}")
    run = subprocess.run([str(exe)], capture_output=True, timeout=30)
    text = run.stdout.decode("utf-8", "replace")
    if run.returncode != 0:
        text += f"\n[进程退出码 {run.returncode}]\n"
    return text, run.returncode


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    lines: list[str] = [
        "# 工单 module-hwcheck/07 行为证据（渲染出的整份 main.c 真编真跑）", "",
        f"主机编译器：{GCC}",
        "被测对象：`render_main_c(..., generic=[sht20 通用小节])` 的**真产出**"
        "（不是替身）；`gpio_*` 由探针仿一条 I2C 总线。",
        "",
    ]
    if not Path(GCC).exists() and shutil.which("gcc") is None:
        lines.append("**没探测到主机 C 编译器**：本探针跑不了（如实标注，不假装）。")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1
    root = Path(tempfile.mkdtemp(prefix="firstep-probe07-"))
    failures = 0
    cases = [
        ("总线上有器件 @0x3C", 0x3C, [
            ("[STUB] sht20_init() 被调用", True),
            ("初始化：sht20_init() 已调用", True),
            ("总线扫描（SHT20_SCL PA6 / SHT20_SDA PA7", True),
            ("应答：0x3C", True),
            ("无应答", False),
            ("未判定：1 项", True),
            ("[STUB] sht20_read()", False),
        ]),
        ("总线上没有器件", -1, [
            ("[STUB] sht20_init() 被调用", True),
            ("无应答", True),
            ("上拉", True),
            ("应答：0x", False),
            ("未判定：1 项", True),
        ]),
    ]
    try:
        for label, slave, expectations in cases:
            workdir = root / ("slave" if slave >= 0 else "empty")
            try:
                text, code = _run(slave_addr=slave, workdir=workdir)
            except Exception as exc:  # noqa: BLE001 —— 证据脚本要结论不要栈
                lines.append(f"## {label}：跑不起来 {type(exc).__name__}: {exc}")
                failures += 1
                continue
            verdict = "符合预期"
            for needle, want in expectations:
                hit = needle in text
                if hit != want:
                    verdict = f"**不符**：{needle!r} 期望 {want}，实得 {hit}"
                    failures += 1
            lines.append(f"## {label}：{verdict}（退出码 {code}）")
            lines.append("```")
            lines.append(text.strip())
            lines.append("```")
            lines.append("")
        ran = len(cases)
        lines.append("## 结论")
        lines.append(f"{ran} 种形态真跑，判红 {failures} 种。")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1 if failures else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
