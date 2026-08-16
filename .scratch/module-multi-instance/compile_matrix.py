"""module-multi-instance/05 双平台编译回归：led 多实例四档 × stm32/mspm0 真编译。

档位（每档双平台）：
  单实例（旧行为）  无 instances        → stm32 LED_RED/YELLOW/GREEN=0/1/2（PC13/14/15）；
                                          mspm0 三宏同脚 PA15
  1 灯               红                  → LED_RED
  2 灯               红+绿               → LED_RED / LED_GREEN
  4 灯（全命名规则） 红+红+绿+状态灯     → LED_RED / LED_RED_2 / LED_GREEN / LED_1

编译口径（module-polish/04 同款）：0 error 硬门槛；模块自身 warning=0；syscfg
ovsRate 基线 warning 允许并记录。产物核对每档：led_instances.h 通道宏值逐项
对上期望列；每实例 led_init 落 main.c（4 灯含 LED_RED_2 / LED_1 不误占位）；
旧单实例行为一致 + pin_config.h / syscfg 逐字节不写（红证：diff 空）。

产物：
  .scratch/module-multi-instance/matrix_results.md   摘要
  .scratch/module-multi-instance/matrix/<tier>/<platform>/{build.log,led_instances.h,diff.txt}
只编译验证，不改生产代码。
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log,
    compile_passed,
    find_ccs_tools,
    find_make,
    find_uv4,
)
from contest_generator.generator import generate  # noqa: E402
from contest_generator.manifest import ModuleManifest  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import ModuleInstance  # noqa: E402

HERE = Path(__file__).parent
LIB = REPO / "library"
MODULES = LIB / "modules"
LED = ModuleManifest.load(MODULES / "led")
MATRIX = HERE / "matrix"
RESULTS = HERE / "matrix_results.md"

GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"

BASELINE_WARNING_MARKERS = (
    "ovsRate",
    "higher oversampling rate",
)


def _inst(*items: ModuleInstance) -> dict[str, tuple[ModuleInstance, ...]]:
    return {"led": tuple(items)}


# 四档：instances + 期望通道宏列（按展开顺序，值 = 0..N-1）
TIERS = [
    {
        "slug": "single",
        "label": "单实例（旧行为）",
        "instances": None,
        "macros": ["LED_RED", "LED_YELLOW", "LED_GREEN"],
    },
    {
        "slug": "1-led",
        "label": "1 灯",
        "instances": _inst(ModuleInstance(name="红灯", variant="red")),
        "macros": ["LED_RED"],
    },
    {
        "slug": "2-led",
        "label": "2 灯",
        "instances": _inst(
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="绿灯", variant="green"),
        ),
        "macros": ["LED_RED", "LED_GREEN"],
    },
    {
        "slug": "4-led",
        "label": "4 灯（全命名规则）",
        "instances": _inst(
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="红灯2", variant="red"),
            ModuleInstance(name="绿灯", variant="green"),
            ModuleInstance(name="状态灯"),
        ),
        "macros": ["LED_RED", "LED_RED_2", "LED_GREEN", "LED_1"],
    },
]


def _stm32_main(macros: list[str]) -> str:
    calls = "\n".join(f"    led_init({macro});" for macro in macros)
    return (
        '#include "ml_led.h"\n'
        "\n"
        "int main(void)\n"
        "{\n"
        f"{calls}\n"
        "    while (1) {}\n"
        "}\n"
    )


def _mspm0_main(macros: list[str]) -> str:
    calls = "\n".join(f"    led_init({macro});" for macro in macros)
    return (
        '#include "ti_msp_dl_config.h"\n'
        '#include "led.h"\n'
        "\n"
        "int main(void)\n"
        "{\n"
        "    /* SYSCFG_DL_init(); */\n"
        f"{calls}\n"
        "    while (1) {}\n"
        "}\n"
    )


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def _header_macro_values(header: str) -> dict[str, str]:
    """led_instances.h 里 `#define LED_X  N` 的通道索引映射（仅收通道索引段；
    排除 LED_CHANNEL_* 的 COUNT/每通道 PORT/PIN 表宏）。"""
    out: dict[str, str] = {}
    for line in header.splitlines():
        m = re.match(r"#define\s+(LED_[A-Z0-9_]+)\s+(\d+)\s*$", line)
        if m and not m.group(1).startswith("LED_CHANNEL_"):
            out[m.group(1)] = m.group(2)
    return out


def _verify_header(tier: dict, header: str, platform: str) -> list[str]:
    """核对通道宏值逐项对上期望列，返回差异描述列表（空 = 通过）。"""
    values = _header_macro_values(header)
    problems: list[str] = []
    for index, macro in enumerate(tier["macros"]):
        got = values.get(macro)
        if got != str(index):
            problems.append(
                f"{platform} 通道宏 {macro} 期望值 {index}，实际 {got!r}"
            )
    # 期望列之外不应有额外的通道索引宏（防止误多生成）
    extras = set(values) - set(tier["macros"])
    if extras:
        problems.append(f"{platform} 出现未预期的通道宏：{sorted(extras)}")
    return problems


def _verify_single_instance_byte_identical(out: Path, platform: str) -> list[str]:
    """旧单实例：多实例渲染零写侧变化。

    led_instances.h（多实例渲染产物文件）逐字节不写（stm32 = 母版默认 / mspm0 =
    库内默认，复制即就位）；pin_config.h 逐字节不写（stm32，pinwriter 不动）。
    mspm0 syscfg 不追「逐字节 = 母版」——syscfg-prune/01 是独立特性、会按选中
    模块裁剪未选实例（与多实例无关）；这里核对的是「多实例渲染没追加 LED_<n>
    GPIO 实例」（空计划 → _write_syscfg_for_plan 不写）。
    """
    problems: list[str] = []
    if platform == PLATFORM_STM32:
        header_src = LIB / "masters" / "stm32" / "led_instances.h"
        header_dst = out / "led_instances.h"
        pin_src = LIB / "masters" / "stm32" / "pin_config.h"
        pin_dst = out / "pin_config.h"
        checks = [
            ("led_instances.h", header_src, header_dst),
            ("pin_config.h", pin_src, pin_dst),
        ]
        for label, src, dst in checks:
            if _norm(src.read_text(encoding="utf-8", errors="replace")) != _norm(
                dst.read_text(encoding="utf-8", errors="replace")
            ):
                problems.append(f"{label} 逐字节不写被破坏")
    else:
        header_src = MODULES / "led" / "code" / "led_instances.h"
        header_dst = out / "modules" / "led" / "code" / "led_instances.h"
        if _norm(header_src.read_text(encoding="utf-8", errors="replace")) != _norm(
            header_dst.read_text(encoding="utf-8", errors="replace")
        ):
            problems.append("led_instances.h 逐字节不写被破坏")
        # 多实例渲染没追加 LED_<n> GPIO 实例（单实例空计划零写侧变化）
        syscfg = (out / "mspm0.syscfg").read_text(
            encoding="utf-8", errors="replace"
        )
        if re.search(r"^\s*const\s+LED_[2-9]\d*\s*=\s*GPIO\.addInstance", syscfg, re.M):
            problems.append("mspm0 syscfg 被多实例渲染追加了 LED_<n> 实例（空计划不该写）")
    return problems


def _warning_failures(platform: str, output: str) -> list[str]:
    """非基线 warning 行（0 error 前提下）。"""
    if platform == PLATFORM_STM32:
        lines = [
            line for line in output.splitlines()
            if re.search(r"warning|Warning", line)
            and "0 Warning" not in line
        ]
    else:
        lines = [
            line for line in output.splitlines()
            if line.lower().startswith(("warning", "warning:"))
        ]
    return [
        line for line in lines
        if not any(marker.lower() in line.lower() for marker in BASELINE_WARNING_MARKERS)
    ]


def _build_main(tier: dict, platform: str) -> str:
    return _stm32_main(tier["macros"]) if platform == PLATFORM_STM32 else _mspm0_main(tier["macros"])


def main() -> int:
    uv4 = find_uv4()
    ccs = find_ccs_tools()
    make = find_make(GMAKE)
    if uv4 is None or ccs is None or make is None:
        print(f"tools missing uv4={uv4} ccs={ccs} make={make}")
        return 2

    if MATRIX.exists():
        shutil.rmtree(MATRIX)
    MATRIX.mkdir(parents=True)

    rows: list[dict] = []
    for tier in TIERS:
        for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
            tier_dir = MATRIX / tier["slug"] / platform
            out = tier_dir / "out"
            notes: list[str] = []
            problems: list[str] = []
            try:
                generate(
                    platform=platform,
                    manifests=[LED],
                    module_library_dir=MODULES,
                    master_project_dir=LIB / "masters" / platform,
                    output_dir=out,
                    main_c_content=_build_main(tier, platform),
                    ccs_tools=ccs if platform == PLATFORM_MSPM0 else None,
                    instances=tier["instances"],
                )
            except Exception as exc:  # noqa: BLE001
                rows.append({
                    "tier": tier["slug"], "platform": platform,
                    "exit": None, "errors": "-", "verdict": "GEN_FAIL",
                    "note": f"生成异常：{exc}",
                })
                print(f"[GEN_FAIL] {tier['slug']}/{platform}: {exc}")
                continue

            # 产物核对：通道宏值 + 单实例逐字节不写
            if platform == PLATFORM_STM32:
                header_path = out / "led_instances.h"
            else:
                header_path = out / "modules" / "led" / "code" / "led_instances.h"
            header = header_path.read_text(encoding="utf-8", errors="replace")
            (tier_dir / "led_instances.h").write_text(
                header, encoding="utf-8", errors="replace"
            )
            problems += _verify_header(tier, header, platform)
            if tier["instances"] is None:
                problems += _verify_single_instance_byte_identical(out, platform)

            # 真编译
            log = collect_build_log(
                platform,
                out,
                uv4=uv4 if platform == PLATFORM_STM32 else None,
                make=make if platform == PLATFORM_MSPM0 else None,
                timeout=300,
            )
            output = log.run.output or ""
            (tier_dir / "build.log").write_text(
                output, encoding="utf-8", errors="replace"
            )
            ok = compile_passed(platform, log.run.exit_code) is True
            warnings = _warning_failures(platform, output)
            errors = re.findall(r"\b(\d+)\s+error", output, re.I)
            error_count = errors[-1] if errors else "0"

            if not ok:
                problems.append(f"编译失败 exit={log.run.exit_code}")
            if warnings:
                problems.append(f"模块自身 warning：{len(warnings)} 条")
            if tier["instances"] is None:
                notes.append("单实例逐字节不写已核对" if not any(
                    "逐字节不写" in p for p in problems
                ) else "单实例逐字节不写破坏")

            verdict = "PASS" if not problems else "FAIL"
            rows.append({
                "tier": tier["slug"], "platform": platform,
                "exit": log.run.exit_code, "errors": error_count,
                "verdict": verdict,
                "note": "；".join(problems) or "0 error，产物核对通过",
            })
            print(
                f"[{verdict}] {tier['slug']}/{platform} exit={log.run.exit_code} "
                f"errors={error_count} module_warnings={len(warnings)}"
            )
            for p in problems:
                print(f"    - {p}")

    lines = [
        "# module-multi-instance 双平台编译回归结果（工单 05）\n",
        f"| 档 | 平台 | exit | errors | 判定 | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['tier']} | {r['platform']} | {r['exit']} | {r['errors']} "
            f"| {r['verdict']} | {r['note']} |"
        )
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"results: {RESULTS}")

    return 0 if all(r["verdict"] == "PASS" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
