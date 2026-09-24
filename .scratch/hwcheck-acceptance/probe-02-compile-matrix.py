# -*- coding: utf-8 -*-
"""工单 02 的真编译矩阵：改名的每一个实例，mspm0 真编译 **0 error / 0 warning**；
票面点名的组合逐格编；stm32 侧抽验不回归。

为什么必须有这一格：改名改掉的是 **SysConfig 生成的宏名**
（`<实例>_<符号>_<后缀>` → `<实例>_<实例>_<符号>_<后缀>`），模块源码靠文本替换跟着
改；文本替换对不对，只有真编译器说了算（工单 11 的既有纪律：改了 `.syscfg` 就要
复跑编译矩阵）。

矩阵三块：

* **A 票面验收格**：`oled + jy61p / aht10 / bh1750 / sht30`（"屏幕 + 一件传感器"）
  与 `led_beep + gp2y1014au`，另加 `aht10 + bh1750`（环境站，02 顺带打开的那格）；
* **B 逐个改名实例**：凡是引脚符号被改过名的模块，各编一格（含它自己的依赖展开）；
* **C stm32 抽验**：挑几件 stm32 侧与改名实例**同名不同源**的模块（`aht10` /
  `hmc5883l` / `lcd`）——它们在 02 里是**零改动**，编过即证没被顺手动过。

用法：
    python .scratch/hwcheck-acceptance/probe-02-compile-matrix.py [--only 关键词]
读数落 `probe-02-compile-matrix.txt`（先落盘再打印）；产物在 `matrix/`（gitignore）。
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.boards import board_for_platform  # noqa: E402
from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log, compile_passed, find_ccs_tools, find_make, find_uv4,
)
from contest_generator.generator import generate_project  # noqa: E402
from contest_generator.pin_bindings import auto_assign_bindings  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402
from contest_generator.syscfg_instances import INSTANCE_CONSUMERS  # noqa: E402
from contest_generator.syscfg_model import parse_syscfg  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
BASE = REPO / ".scratch" / "hwcheck-acceptance" / "matrix"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    "int main(void)\n"
    "{\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# stm32 侧不带 include：main.c 引用的头必须能在最终工程里解析到（生成门禁），
# 而 stm32 的工具链头不在模块库清单里——本单要的是"模块源码真编译"，不是 main 的
# 头解析，故给一份无 include 的空骨架。
MAIN_C_STM32 = "int main(void)\n{\n    while (1)\n    {\n    }\n}\n"


def renamed_instances() -> dict[str, list[str]]:
    """`实例 → 消费模块`——本轮的射程表（母版名与库内名两侧对不上就算改名了）。

    判据：母版里该实例的引脚符号**带实例前缀**（`AHT10_SCL`）而 manifest 里该角色
    的 id 是原名（`AHT10_SCL` 同名不算）——简单说：凡在 02 改名清单里的实例。
    这里直接用「符号名以 `<实例名>_` 开头」认定，与改名器的规则同源。
    """
    model = parse_syscfg(
        (MASTERS / "mspm0" / "mspm0.syscfg").read_text(encoding="utf-8")
    )
    out: dict[str, list[str]] = {}
    for instance, names in model.pin_names.items():
        prefixed = [n for n in names if n.startswith(f"{instance}_")]
        if prefixed:
            out[instance] = list(INSTANCE_CONSUMERS.get(instance, ()))
    return out


def shapes() -> list[tuple[str, str, tuple[str, ...]]]:
    acceptance = [
        ("A/oled+jy61p", ("led", "delay", "debug_uart", "oled", "jy61p")),
        ("A/oled+aht10", ("led", "delay", "debug_uart", "oled", "aht10")),
        ("A/oled+bh1750", ("led", "delay", "debug_uart", "oled", "bh1750")),
        ("A/oled+sht30", ("led", "delay", "debug_uart", "oled", "sht30")),
        ("A/led_beep+gp2y1014au", ("led_beep", "gp2y1014au")),
        ("A/aht10+bh1750", ("led", "delay", "debug_uart", "aht10", "bh1750")),
        ("A/oled+lcd", ("led", "delay", "debug_uart", "oled", "lcd")),
        ("A/rc522+nrf24l01", ("rc522", "nrf24l01")),
        ("A/dht11+ds18b20", ("dht11", "ds18b20")),
        ("A/hx711+rc522", ("hx711", "rc522")),
        ("A/relay+human_ir", ("relay", "human_ir")),
        ("A/jq8900+syn6288", ("jq8900", "syn6288")),
    ]
    per_module = [
        (f"B/{slug}", (slug,)) for slug in sorted(
            {s for slugs in renamed_instances().values() for s in slugs}
        )
    ]
    stm32 = [
        ("C/stm32/aht10", ("aht10", "delay")),
        ("C/stm32/hmc5883l", ("hmc5883l", "delay")),
        ("C/stm32/lcd", ("lcd", "delay")),
    ]
    out: list[tuple[str, str, tuple[str, ...]]] = []
    out += [(label, PLATFORM_MSPM0, slugs) for label, slugs in acceptance]
    out += [(label, PLATFORM_MSPM0, slugs) for label, slugs in per_module]
    out += [(label, PLATFORM_STM32, slugs) for label, slugs in stm32]
    return out


def count_diagnostics(text: str) -> tuple[int, int, int]:
    """(错误数, 告警数, 既有死函数告警数)。

    排除 Keil 的收尾汇总行（`0 Error(s), 0 Warning(s).` 自己就含 `Warning` 子串，
    按行数会把 0 读成 1；local-environment.md 记过这条）。

    第三个数是**与本次改名无关**的既有告警：`rc522.c` 里 `_antenna_off` 是个死静态
    函数（基线版本 `git show HEAD:library/modules/rc522/code/rc522.c` 里同样"定义
    了、没人调"），`-Wunused-function` 会点它——凡编到 rc522 的格都有，不是本单引入。
    """
    errors = warnings = dead = 0
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\s+Error\(s\)", stripped) or stripped.startswith("Build Time"):
            continue
        if re.search(r"\berror\b\s*[:#]", stripped, re.IGNORECASE):
            errors += 1
        elif re.search(r"\bwarning\b\s*[:#]", stripped, re.IGNORECASE):
            warnings += 1
            if "-Wunused-function" in stripped and "rc522.c" in stripped:
                dead += 1
    return errors, warnings, dead


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="只跑标签含该关键词的格")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    selected = [s for s in shapes() if args.only in s[0]]
    lines: list[str] = []
    failed: list[str] = []
    for label, platform, slugs in selected:
        out = BASE / label.replace("/", "-")
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        resolved = resolve_selection(MODULES, platform, list(slugs))
        board = board_for_platform(platform)
        solved = auto_assign_bindings(
            resolved.manifests, platform, board, {},
            resolve_default_conflicts=True,
        )
        try:
            generate_project(
                platform=platform, slugs=list(slugs),
                main_c_content=(
                    MAIN_C_MSPM0 if platform == PLATFORM_MSPM0 else MAIN_C_STM32
                ),
                output_dir=out, module_library_dir=MODULES, masters_dir=MASTERS,
                ccs_tools=find_ccs_tools(), bindings=solved.bindings or None,
            )
        except Exception as exc:  # 生成前拦下 = 这格没打开（要如实报）
            lines.append(f"[生成拦下] {label}：{type(exc).__name__}")
            for detail in str(exc).splitlines()[:3]:
                lines.append("           " + detail.strip()[:150])
            failed.append(label)
            continue
        log = collect_build_log(
            platform, out,
            make=find_make(GMAKE) if platform == PLATFORM_MSPM0 else None,
            uv4=find_uv4() if platform == PLATFORM_STM32 else None,
            timeout=600,
        )
        text = log.run.output or ""
        errors, warnings, dead = count_diagnostics(text)
        own_warnings = warnings - dead
        ok = compile_passed(platform, log.run.exit_code) and not errors and not own_warnings
        note = f"（其中 rc522 既有死函数 {dead} 条）" if dead else ""
        lines.append(
            f"[{'PASS' if ok else 'FAIL'}] {label}：exit={log.run.exit_code}、"
            f"error {errors}、warning {own_warnings}{note}"
        )
        if own_warnings or not ok:
            for line in text.splitlines():
                if re.search(r"\b(warning|error)\b\s*[:#]", line, re.IGNORECASE):
                    lines.append("           " + line.strip()[:160])
        if not ok:
            failed.append(label)

    head = [
        "=== 工单 02 编译矩阵（改名改了生成宏，真编译兜底）===",
        f"格数：{len(selected)}，FAIL：{len(failed)}",
        "",
    ]
    tail = [
        "",
        "=== 结论：" + ("全绿（0 error / 0 warning）" if not failed
                        else "有 FAIL：" + "、".join(failed)) + " ===",
    ]
    report = "\n".join(head + lines + tail) + "\n"
    path = Path(args.out) if args.out else BASE.parent / "probe-02-compile-matrix.txt"
    path.write_text(report, encoding="utf-8")     # 先落盘
    print(report)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
