# -*- coding: utf-8 -*-
"""工单 module-hwcheck/06 的**行为红证**：把「真库既有命令台 + 渲染出的命令台」编起来真跑。

用法：python .scratch/module-hwcheck/probe-06-console-behaviour.py

## 为什么要有这一支（票面两条硬要求都靠它证）

票面写着：**既有 `r/y/g/o/b<N>` 语义一个字节不动**、**新命令只追加**。文本断言
证明不了这两件事——"渲染出的 main.c 里没有重写那五条命令"只能说明我们没写，
不能说明**敲 `r` 时真跑的是库内那份代码、而且我们的命令台没抢**。

所以本探针把三份东西编进**同一个可执行文件**：

1. **库内 `debug_uart.c` 的真源码**（`library/modules/debug_uart/code/debug_uart.c`，
   原样 `-I` 编进来）——既有 `debug_cmd_poll()` 与新增的 peek / consume 都是真身；
2. **渲染器真产出的命令台运行时**（`hwcheck_console.render_console_runtime`）；
3. 一层**桩**：串口寄存器（`DEBUG_UART_INST->DR`）、`gpio_set` / `delay_ms` /
   `uart_sendstr`（把调用打印出来，于是"谁动了灯"看得见）、以及框架那几个
   报告函数。

喂字符走的是**真 RX 中断处理**（往 `DEBUG_UART_INST->DR` 写一个字符 → 调
`debug_uart_rx_handler()`），命令循环走**真主循环顺序**（先 `hwcheck_console_poll()`
再 `debug_cmd_poll()`）——与渲染出的 main.c 一字不差。

判据（每条都双向：该出现的必须出现、不该出现的一个都不许有）：

| 输入 | 该出现 | 不许出现 |
|---|---|---|
| `l` / `L` | 复测回显三段 + `led` 小节体 | 库内命令的痕迹（`gpio_set`） |
| `m` | `ml_mpu6050` 小节体 | 同上 |
| `?` | 帮助（既有五条 + 配方命令 + 帮助自己） | 库内命令的痕迹 |
| `z` | `[未知命令] z` + 帮助 | 库内命令的痕迹（未知也被认领，不再打库内那句 `? r/g/y/o/b<N>`） |
| `r` | **`gpio_set(...,13,1)`**（库内红灯分支真跑了） | 任何 `[复测]`（我们的命令台没抢） |
| `b50` | 库内蜂鸣 `50ms` | 任何 `[复测]` |
| 空输入 | 什么都不做 | 全部 |

输出：probe-06-console-behaviour.txt
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.hwcheck_console import (  # noqa: E402
    build_console_table,
    render_console_runtime,
)
from contest_generator.hwcheck_recipe import (  # noqa: E402
    interface_names,
    load_recipes,
    resolve_sections,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.master_store import master_project_dir  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402
from contest_generator.treewalk import iter_project_files  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe-06-console-behaviour.txt"
GCC = shutil.which("gcc") or r"C:\mingw64\bin\gcc.exe"
MODULE_CODE = REPO / "library" / "modules" / "debug_uart" / "code"

# 桩头：真 debug_uart.c 的四个 include（headfile / config / pin_config 是工程头，
# 这里给最小替身；debug_uart.h 用**真的**，从模块目录找）。
STUB_HEADFILE = r"""
#ifndef HWCHECK_PROBE06_HEADFILE_H
#define HWCHECK_PROBE06_HEADFILE_H
#include <stdint.h>
void uart_pin_init_ex(int uart, int txgpio, int txpin, int rxgpio, int rxpin);
void uart_sendstr(int uart, char *str);
void gpio_set(int port, int pin, int level);
void delay_ms(uint32_t ms);
#endif
"""

STUB_CONFIG = "#ifndef HWCHECK_PROBE06_CONFIG_H\n#define HWCHECK_PROBE06_CONFIG_H\n#endif\n"

# 引脚 / 实例宏：值只要不与断言冲突即可；gpio_set 会把引脚号打出来，
# 所以断言能点名"红灯那一支真跑了"。
STUB_PIN_CONFIG = r"""
#ifndef HWCHECK_PROBE06_PIN_CONFIG_H
#define HWCHECK_PROBE06_PIN_CONFIG_H
typedef struct { volatile unsigned int DR; } probe06_uart_t;
extern probe06_uart_t probe06_uart0;
#define DEBUG_UART_INST (&probe06_uart0)
#define DEBUG_UART 2
#define DEBUG_UART_TX_GPIO 0
#define DEBUG_UART_TX_Pin 2
#define DEBUG_UART_RX_GPIO 0
#define DEBUG_UART_RX_Pin 3
#define LED_PORT 0
#define LED_RED_PIN 13
#define LED_YELLOW_PIN 14
#define LED_GREEN_PIN 15
#define BUZZER_GPIO 1
#define BUZZER_PIN 0
#endif
"""

# 桩实现：外设动作全部打印（"谁动了灯"看得见），报告函数把内容回显到 stdout。
STUB_IMPL = r"""
#include "headfile.h"
#include "pin_config.h"
#include <stdio.h>

probe06_uart_t probe06_uart0;

void uart_pin_init_ex(int uart, int txgpio, int txpin, int rxgpio, int rxpin)
{
    (void)uart; (void)txgpio; (void)txpin; (void)rxgpio; (void)rxpin;
}
void uart_sendstr(int uart, char *str)
{
    /* 库内既有命令的提示语从这里出去（DEBUG_PRINTF → debug_uart_send）——
       打印出来，于是"库内到底说了什么"看得见。 */
    (void)uart;
    printf("LIB-UART: %s", str);
}
void gpio_set(int port, int pin, int level)
{
    printf("LIB: gpio_set(port=%d, pin=%d, level=%d)\n", port, pin, level);
}
void delay_ms(uint32_t ms) { printf("LIB: delay_ms(%u)\n", (unsigned)ms); }

/* 框架侧的报告函数（输出通道）：把命令台打出来的每个字回显出来。 */
void hwcheck_report(const char *text) { fputs(text, stdout); }
void hwcheck_newline(void) { fputc('\n', stdout); }
void hwcheck_report_int(int value) { printf("%d", value); }
void hwcheck_section(const char *title) { printf("== %s ==\n", title); }
void hwcheck_detail(const char *text) { printf("   detail: %s\n", text); }
void hwcheck_verdict(int ok, const char *trouble)
{
    printf("   verdict: %s\n", ok ? "OK" : "FAIL");
    if (!ok) printf("   trouble: %s\n", trouble);
}
void hwcheck_verdict_probe_none(const char *hint) { printf("   none: %s\n", hint); }
"""

# 一节小节的"体"：命令台复测时调它——桩把它标出来，证明"复测真的跑了那一节"。
SECTION_STUB = """
static void hwcheck_check_%(slug)s(void) { printf("SECTION-BODY: %(slug)s\\n"); }
"""

HARNESS_MAIN = r"""
/* 真 RX 中断处理：往 DR 写一个字符再调 handler（与板上同一条路）。 */
static void feed(const char *line)
{
    while (*line != '\0')
    {
        probe06_uart0.DR = (unsigned int)(unsigned char)(*line);
        debug_uart_rx_handler();
        line++;
    }
}

int main(int argc, char **argv)
{
    const char *line = (argc > 1) ? argv[1] : "";
    feed(line);
%(loop)s
    printf("--END--\n");
    return 0;
}
"""

LOOP_IN_ORDER = (
    "    hwcheck_console_poll();   /* 先我们的（渲染出的 main.c 就是这个顺序） */\n"
    "    debug_cmd_poll();         /* 再库内的（既有 r/y/g/o/b，一个字节没动） */"
)
# 反证用：顺序倒过来。库内 poll 先把缓冲清空，我们的命令台就永远认不出配方命令
# ——渲染出的 main.c 若写成这个顺序，`l` 会毫无反应（本探针用它证明那条顺序断言
# 不是空话：同一份命令台代码，只换顺序就复测不了）。
LOOP_REVERSED = (
    "    debug_cmd_poll();         /* 反证：先库内 */\n"
    "    hwcheck_console_poll();   /* 再我们的（此时缓冲已被清空） */"
)


def _table():
    """真库真配方 → 该平台的命令表（判据读真数据，不手写替身）。"""
    modules = REPO / "library" / "modules"
    manifests = list_modules(modules)
    master = master_project_dir(REPO / "library" / "masters", PLATFORM_STM32)
    headers = [] if not master.is_dir() else [
        (path.relative_to(master).as_posix(),
         path.read_text(encoding="utf-8", errors="replace"))
        for path in iter_project_files(master, pattern="*.h")
    ]
    interfaces = {
        PLATFORM_STM32: interface_names(manifests, modules, PLATFORM_STM32, headers)
    }
    recipes = load_recipes(modules, manifests, interfaces)
    sections = resolve_sections(
        PLATFORM_STM32, ("led", "oled", "ml_mpu6050"), recipes, manifests
    )
    return build_console_table(sections)


def _build(workdir: Path, *, reversed_order: bool = False) -> Path:
    """把真库 + 渲染出的命令台 + 桩编成一个可执行文件。

    `reversed_order=True` = 反证用：主循环里先调库内 poll（它会清空缓冲）。
    """
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "headfile.h").write_text(STUB_HEADFILE, encoding="utf-8")
    (workdir / "config.h").write_text(STUB_CONFIG, encoding="utf-8")
    (workdir / "pin_config.h").write_text(STUB_PIN_CONFIG, encoding="utf-8")
    (workdir / "stub.c").write_text(STUB_IMPL, encoding="utf-8")
    table = _table()
    body = "\n".join(render_console_runtime(table))
    sections = "\n".join(
        SECTION_STUB % {"slug": entry.slug} for entry in table.entries
    )
    harness = (
        '#include "headfile.h"\n'
        '#include "pin_config.h"   /* 桩：串口寄存器（喂字符用） */\n'
        '#include "debug_uart.h"\n'
        + sections + "\n" + body + "\n"
        + HARNESS_MAIN % {"loop": LOOP_REVERSED if reversed_order else LOOP_IN_ORDER}
    )
    source = workdir / "harness.c"
    source.write_text(harness, encoding="utf-8")
    exe = workdir / "harness.exe"
    build = subprocess.run(
        [GCC, "-std=c99", "-w",
         "-I", str(workdir),          # 桩头优先（headfile / config / pin_config）
         "-I", str(MODULE_CODE),      # 真 debug_uart.h
         str(source), str(workdir / "stub.c"),
         str(MODULE_CODE / "debug_uart.c"),   # ← **真库源码**
         "-o", str(exe)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if build.returncode != 0:
        raise RuntimeError(f"gcc 编译失败：\n{build.stdout}\n{build.stderr}")
    return exe


def _run(exe: Path, line: str) -> str:
    run = subprocess.run([str(exe), line], capture_output=True)
    return run.stdout.decode("utf-8", "replace")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    lines: list[str] = [
        "# 工单 module-hwcheck/06 行为红证（真库既有命令台 + 渲染出的命令台，同一跑）",
        "",
        f"主机编译器：{GCC}",
        "编进来的三样：① 真 `library/modules/debug_uart/code/debug_uart.c`；"
        "② `render_console_runtime` 的真产出；③ 外设桩（`gpio_set` 打印）。",
        "喂字符走真 RX 中断（写 `DEBUG_UART_INST->DR` → `debug_uart_rx_handler()`），"
        "命令循环顺序与渲染出的 main.c 一致。",
        "",
    ]
    if not Path(GCC).exists() and shutil.which("gcc") is None:
        lines.append("**没探测到主机 C 编译器**：本探针跑不了（如实标注，不假装）。")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1
    # (标签, 输入, [(needle, 该不该出现), …])
    scenarios: list[tuple[str, str, list[tuple[str, bool]]]] = [
        ("复测 led（小写）", "l",
         [("== [复测] led ==", True), ("detail: 测的是：", True),
          ("SECTION-BODY: led", True), ("LIB:", False)]),
        ("复测 led（大写也认）", "L",
         [("SECTION-BODY: led", True), ("LIB:", False)]),
        ("复测 ml_mpu6050", "m",
         [("== [复测] ml_mpu6050 ==", True), ("SECTION-BODY: ml_mpu6050", True),
          ("LIB:", False)]),
        ("帮助命令", "?",
         [("[帮助] 可用命令", True), ("既有：r 红灯亮", True),
          ("  l  led：", True), ("  ?  显示这份帮助", True), ("LIB:", False)]),
        ("未知命令", "z",
         [("[未知命令] z", True), ("[帮助] 可用命令", True), ("LIB:", False)]),
        ("既有命令 r（库内跑）", "r",
         [("LIB: gpio_set(port=0, pin=13, level=1)", True),
          ("LIB: gpio_set(port=0, pin=14, level=0)", True),
          ("[复测]", False), ("SECTION-BODY", False), ("[未知命令]", False)]),
        ("既有命令 b50（库内跑，带参数）", "b50",
         [("LIB: delay_ms(50)", True), ("[复测]", False), ("SECTION-BODY", False)]),
        ("空输入（什么都没敲）", "",
         [("SECTION-BODY", False), ("LIB:", False), ("[复测]", False),
          ("[未知命令]", False), ("[帮助]", False)]),
    ]
    root = Path(tempfile.mkdtemp(prefix="firstep-probe06b-"))
    failures = 0
    try:
        exe = _build(root)
        for label, typed, checks in scenarios:
            try:
                transcript = _run(exe, typed)
            except Exception as exc:  # noqa: BLE001 —— 证据脚本要结论不要栈
                lines.append(f"## {label}：跑不起来 —— {exc}")
                failures += 1
                continue
            bad = [
                f"{'应出现' if expected else '不该出现'}「{needle}」"
                for needle, expected in checks
                if (needle in transcript) != expected
            ]
            lines.append(f"## 敲 `{typed or '(空)'}` —— {label}："
                         f"{'PASS' if not bad else 'FAIL'}"
                         + ("" if not bad else " —— " + "；".join(bad)))
            if bad:
                failures += 1
            lines.append("```")
            lines.extend(transcript.strip("\n").splitlines()[:16])
            lines.append("")
            lines.append("")
        # 反证：同一份命令台代码，只把主循环顺序倒过来 → 配方命令复测不了。
        try:
            reversed_exe = _build(root / "reversed", reversed_order=True)
            reversed_transcript = _run(reversed_exe, "l")
            caught = (
                "SECTION-BODY: led" not in reversed_transcript
                and "? r/g/y/o/b<N>" in reversed_transcript
            )
            lines.append("## 反证：把主循环顺序倒过来（先库内 poll 再我们的）敲 `l`："
                         f"{'PASS' if caught else 'FAIL'}")
            if not caught:
                failures += 1
            lines.append("```")
            lines.extend(reversed_transcript.strip("\n").splitlines()[:12])
            lines.append("```")
            lines.append("")
            lines.append(
                "顺序倒过来就没法复测（库内 poll 先把缓冲清空），"
                "所以渲染出的 main.c 那条「先 hwcheck_console_poll() 再 "
                "debug_cmd_poll()」不是风格问题，是功能前提——"
                "守卫用例 `test_main_polls_our_console_before_the_library_poll` 钉的就是它。"
            )
            lines.append("")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"## 反证：跑不起来 —— {exc}")
            failures += 1
        lines.append("## 结论")
        lines.append(
            f"{len(scenarios)} 次真跑，{len(scenarios) - failures} 次符合预期、"
            f"{failures} 次不符。"
            + ("既有五条命令走的是**库内真源码**（`gpio_set` / `delay_ms` 是它打的），"
               "配方命令走的是命令台；两边互不抢字符。"
               if not failures else "**有形态不符**。")
        )
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1 if failures else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
