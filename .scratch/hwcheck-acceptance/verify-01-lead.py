# -*- coding: utf-8 -*-
"""工单 01 的**领单复核**（不同于探针的第二条路线）：判据面 / 确定性 / 平台边界。

为什么另起一支：`probe-01-*.py` 验的是"三条路端到端 + 真编译"，本支验的是**域层别的
入口**——判据的**精确性**（放行面是按裁剪后实例现算的，不是前缀白名单）、
**确定性补行**的三种输入形态、以及 **stm32 一个字节都不受影响**。两条路线互不覆盖：

* 判据精确性：`SYSCFG_DL_LCD_init()` 在 `lcd` **没选中**时必须红；选中时放行；
  拼错名 / 条件生成的 `saveConfiguration` 必须红；**母版读不到时不静默放行**。
* 确定性：出稿没写 → 补一行；写了活的 → 不重复；只写了注释占位 → 仍恰好一行活调用。
* 平台边界：stm32 路径不得出现 `SYSCFG_DL_init`（那边是 `SystemInit` 的世界）。

用法：`python .scratch/hwcheck-acceptance/verify-01-lead.py [--out FILE]`（只读，
不改任何库内文件；先落盘再打印——本机控制台是 GBK）。
"""
import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.generator import (  # noqa: E402
    ModuleCorpus, _check_main_calls, UndefinedCallsError,
)
from contest_generator.hwcheck import HwCheckConfig, render_main_c  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.skeleton import (  # noqa: E402
    build_skeleton_interfaces, generate_skeleton, strip_comments,
)

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
MASTER_SYSCFG = (MASTERS / "mspm0" / "mspm0.syscfg").read_text(encoding="utf-8")


class _StubLLM:
    """只回一段 main.c 的假 LLM（键位与 LLM.generate_main_skeleton 对齐）。"""

    def __init__(self, main_c: str) -> None:
        self.main_c = main_c

    def generate_main_skeleton(self, *_args, **_kwargs) -> str:
        return self.main_c


def _live_calls(main_c: str, name: str = "SYSCFG_DL_init") -> int:
    """剥注释后的活调用次数（注释里的旧占位不算）。"""
    import re

    return len(re.findall(rf"\b{name}\s*\(", strip_comments(main_c)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    lines: list[str] = ["=== 工单 01 领单复核（判据精确性 / 确定性 / 平台边界）===", ""]
    ok_all = True

    def record(label: str, ok: bool, detail: str = "") -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"：{detail}" if detail else ""))

    by_slug = {m.slug: m for m in list_modules(MODULES)}

    def corpus(slugs: list[str], main_c: str, master_syscfg=MASTER_SYSCFG) -> ModuleCorpus:
        """语料：`master_project_dir` 给**真母版树**（门禁那一块要求母版树里真有
        `mspm0.syscfg`——`_corpus_syscfg_interface_blocks` 的"不猜"守卫；给一个
        没有该文件的空目录就是"不并入"，那是另一条被测行为）。"""
        return ModuleCorpus(
            platform=PLATFORM_MSPM0,
            modules=tuple((s, ()) for s in slugs),
            missing_platforms=(),
            missing_files=(),
            master_headers=(),
            master_search_dirs=(),
            search_dir_headers=(),
            master_project_dir=MASTERS / "mspm0",
            main_c=main_c,
            master_syscfg=master_syscfg,
        )

    # ---- 判据精确性（域层门禁直调）----
    def gate(slugs: list[str], call: str, master_syscfg=MASTER_SYSCFG) -> str:
        body = f'#include "ti_msp_dl_config.h"\nint main(void) {{\n    {call};\n    while (1) {{}}\n}}\n'
        try:
            _check_main_calls(corpus(slugs, body, master_syscfg))
            return ""
        except UndefinedCallsError as exc:
            return str(exc)
        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {exc}"

    msg = gate(["led", "delay"], "SYSCFG_DL_init()")
    record("骨架/赛题门禁放行恒有的 SYSCFG_DL_init()", msg == "", msg[:90])

    msg = gate(["led", "delay"], "SYSCFG_DL_LCD_init()")
    record("**没选 lcd** 时 SYSCFG_DL_LCD_init() 仍红（精确判据，不是前缀白名单）",
           "SYSCFG_DL_LCD_init" in msg, msg[:90])

    # GPIO 实例**没有**实例级 init（109 份真产物实测 0/109）——选中它也不放行。
    # 这是 01 双轴评审抓到的过度放行：不排除就会让一条真会编不过的调用过关。
    msg = gate(["led", "delay", "lcd"], "SYSCFG_DL_LCD_init()")
    record("**选中 lcd** 也不放行 SYSCFG_DL_LCD_init()（GPIO 实例无实例级 init）",
           "SYSCFG_DL_LCD_init" in msg, msg[:90])

    msg = gate(["led", "delay", "oled"], "SYSCFG_DL_OLED_SPI_init()")
    record("GPIO 实例 OLED_SPI 的 init 不放行（0/109）",
           "SYSCFG_DL_OLED_SPI_init" in msg, msg[:90])

    # 外设实例：选中就放行（OLED 是 I2C 实例、DEBUG_UART 是 UART 实例）
    msg = gate(["led", "delay", "oled"], "SYSCFG_DL_OLED_init()")
    record("选中 oled 时 SYSCFG_DL_OLED_init() 放行（I2C 实例）", msg == "", msg[:90])

    msg = gate(["led", "delay"], "SYSCFG_DL_OLED_init()")
    record("没选 oled 时 SYSCFG_DL_OLED_init() 仍红", "SYSCFG_DL_OLED_init" in msg, msg[:90])

    msg = gate(["led", "delay", "debug_uart"], "SYSCFG_DL_DEBUG_UART_init()")
    record("选中 debug_uart 时 SYSCFG_DL_DEBUG_UART_init() 放行（UART 实例）",
           msg == "", msg[:90])

    msg = gate(["led", "delay"], "SYSCFG_DL_TYPO_init()")
    record("拼错名 SYSCFG_DL_TYPO_init() 仍红", "SYSCFG_DL_TYPO_init" in msg, msg[:90])

    msg = gate(["led", "delay"], "SYSCFG_DL_saveConfiguration()")
    record("条件生成的 saveConfiguration() 不放行（109 份里只有 65 份有）",
           "SYSCFG_DL_saveConfiguration" in msg, msg[:90])

    msg = gate([], "SYSCFG_DL_TOTALLY_MADE_UP()")
    record("凭空造的名字仍红（门禁没被削弱）", "SYSCFG_DL_TOTALLY_MADE_UP" in msg, msg[:90])

    # 语料里没有 syscfg 文本 = 不并入那一块（不猜）——退回现状：恒有的名字也判红。
    # 这是刻意行为（域层"不静默放行"），单独钉一条，免得哪天被当成 bug 改掉。
    # 也顺带钉住"判据吃语料、不读盘"（01 评审整改）：语料文本为空时不看盘上母版。
    try:
        _check_main_calls(ModuleCorpus(
            platform=PLATFORM_MSPM0,
            modules=(("led", ()), ("delay", ())),
            missing_platforms=(), missing_files=(), master_headers=(),
            master_search_dirs=(), search_dir_headers=(),
            master_project_dir=MASTERS / "mspm0",  # 盘上有母版
            main_c='int main(void) { SYSCFG_DL_init(); while (1) {} }\n',
            master_syscfg="",  # 但语料里没有 syscfg 文本
        ))
        record("语料里没有 syscfg 文本时不静默放行（也不去读盘）", False, "居然放行了")
    except UndefinedCallsError:
        record("语料里没有 syscfg 文本时不静默放行（也不去读盘）", True)

    # ---- 确定性（骨架这一路）----
    no_init = (
        '#include "ti_msp_dl_config.h"\n'
        "int main(void)\n{\n    led_init();\n    while (1) {}\n}\n"
    )
    commented = (
        '#include "ti_msp_dl_config.h"\n'
        "int main(void)\n{\n    /* SYSCFG_DL_init(); */\n    while (1) {}\n}\n"
    )
    with_init = (
        '#include "ti_msp_dl_config.h"\n'
        "int main(void)\n{\n    SYSCFG_DL_init();\n    while (1) {}\n}\n"
    )
    for label, text, want in (
        ("出稿没写 → 补恰好一行", no_init, 1),
        ("出稿写了活的 → 不重复", with_init, 1),
        ("出稿只写了注释占位 → 仍恰好一行活调用", commented, 1),
    ):
        manifests = [by_slug[s] for s in ("led", "delay")]
        produced, _blocked = generate_skeleton(
            _StubLLM(text), "题面", manifests, PLATFORM_MSPM0, MODULES,
            master_project_dir=MASTERS / "mspm0",
        )
        got = _live_calls(produced)
        record(f"骨架确定性：{label}", got == want, f"活调用 {got} 处（期望 {want}）")
        if text is commented:
            lines.append("      产出样张（只写了注释占位那一格）：")
            lines.extend("        " + row for row in produced.splitlines())

    # ---- 平台边界 ----
    stm32_main = (
        '#include "headfile.h"\n'
        "int main(void)\n{\n    while (1) {}\n}\n"
    )
    stm32_manifests = [by_slug[s] for s in ("led", "delay")]
    produced, _blocked = generate_skeleton(
        _StubLLM(stm32_main), "题面", stm32_manifests, PLATFORM_STM32, MODULES,
        master_project_dir=MASTERS / "stm32",
    )
    record("stm32 骨架不插 SYSCFG_DL_init（平台边界）",
           _live_calls(produced) == 0, f"活调用 {_live_calls(produced)} 处")

    # ---- 检测页这一路（渲染器 + 清单文案）----
    code = render_main_c(HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=True))
    record("检测页渲染器输出活调用", _live_calls(code) == 1, f"活调用 {_live_calls(code)} 处")
    record("检测页不再叫学生「取消注释」", "取消注释" not in code)

    stm32_code = render_main_c(HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=True))
    record("检测页 stm32 不出现 SYSCFG_DL_init",
           "SYSCFG_DL_init" not in stm32_code)

    lines.append("")
    lines.append("=== 结论：" + ("全部成立" if ok_all else "有 FAIL（见上）") + " ===")
    report = "\n".join(lines) + "\n"
    path = Path(args.out) if args.out else Path(__file__).with_suffix(".txt")
    path.write_text(report, encoding="utf-8")
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
