"""key-multi-instance/07 双平台编译矩阵：key 多实例档 × stm32/mspm0 真编译。

档位（每档双平台）：
  single（旧行为）  无 instances        → KEY_START=0（单通道默认，PA2/PB3）
  2-key             start + stop        → KEY_START / KEY_STOP（stm32 具体脚、
                                            mspm0 KEY_2 输入实例）
  3-key（2026F）    3 个通用键          → KEY_1 / KEY_2 / KEY_3

编译口径（module-polish/04 同款）：0 error 硬门槛；模块自身 warning=0；syscfg
基线 warning 允许并记录。产物核对每档：key_instances.h 通道宏值逐项对上期望列
（无便捷宏）；单实例档额外核对逐字节不写（stm32 = 母版默认 / mspm0 = 库内默认）
与 syscfg 无 KEY_<n> 追加实例（空计划零写侧变化）。

产物：
  .scratch/key-multi-instance/matrix_results.md   摘要
  .scratch/key-multi-instance/matrix/<tier>/<platform>/{build.log,key_instances.h}
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
KEY = ModuleManifest.load(MODULES / "key")
MATRIX = HERE / "matrix"
RESULTS = HERE / "matrix_results.md"

GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"

BASELINE_WARNING_MARKERS = (
    "ovsRate",
    "higher oversampling rate",
)


def _inst(*items: ModuleInstance) -> dict[str, tuple[ModuleInstance, ...]]:
    return {"key": tuple(items)}


# 四档：instances + 期望通道宏列（按展开顺序，值 = 0..N-1）
TIERS = [
    {
        "slug": "single",
        "label": "单实例（旧行为）",
        "instances": None,
        "macros": ["KEY_START"],
    },
    {
        "slug": "2-key",
        "label": "2 键（启动 + 停止）",
        "instances": _inst(
            ModuleInstance(name="启动键", variant="start"),
            ModuleInstance(name="停止键", variant="stop"),
        ),
        "macros": ["KEY_START", "KEY_STOP"],
    },
    {
        "slug": "3-key",
        "label": "3 键（2026F 通用）",
        "instances": _inst(
            ModuleInstance(name="按钮1"),
            ModuleInstance(name="按钮2"),
            ModuleInstance(name="按钮3"),
        ),
        "macros": ["KEY_1", "KEY_2", "KEY_3"],
    },
]


def _stm32_main(macros: list[str]) -> str:
    reads = "\n".join(
        f"    {{ uint8_t k = get_key_state({macro}); (void)k; }}" for macro in macros
    )
    return (
        '#include "key_stm32.h"\n'
        "\n"
        "int main(void)\n"
        "{\n"
        "    key_init();\n"
        f"{reads}\n"
        "    while (1) {}\n"
        "}\n"
    )


def _mspm0_main(macros: list[str]) -> str:
    reads = "\n".join(
        f"    {{ uint8_t k = get_key_state({macro}); (void)k; }}" for macro in macros
    )
    return (
        '#include "ti_msp_dl_config.h"\n'
        '#include "key.h"\n'
        "\n"
        "int main(void)\n"
        "{\n"
        "    key_init();\n"
        f"{reads}\n"
        "    while (1) {}\n"
        "}\n"
    )


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def _header_macro_values(header: str) -> dict[str, str]:
    """key_instances.h 里 `#define KEY_X  N` 的通道索引映射（排除 COUNT/
    每通道 PORT/PIN 表宏）。"""
    out: dict[str, str] = {}
    for line in header.splitlines():
        m = re.match(r"#define\s+(KEY_[A-Za-z0-9_]+)\s+(\d+)\s*$", line)
        if m and not m.group(1).startswith("KEY_CHANNEL_"):
            out[m.group(1)] = m.group(2)
    return out


# 默认单通道表的索引别名宏（契约值 = 位置序 1..4，运行时越界钳回首通道——
# 与 led 单通道默认别名先例一致）；出现即核对契约值，不算多余
DEFAULT_ALIAS_MACROS = {"KEY_STOP": "1", "KEY_MODE": "2", "KEY_SET": "3", "KEY_1": "4"}


def _verify_header(tier: dict, header: str, platform: str) -> list[str]:
    """核对通道宏值逐项对上期望列，返回差异描述列表（空 = 通过）。

    默认别名宏（KEY_STOP = 1 等）只核契约值，不计入「未预期通道宏」。
    """
    values = _header_macro_values(header)
    problems: list[str] = []
    for index, macro in enumerate(tier["macros"]):
        got = values.get(macro)
        if got != str(index):
            problems.append(
                f"{platform} 通道宏 {macro} 期望值 {index}，实际 {got!r}"
            )
    for macro, expected in DEFAULT_ALIAS_MACROS.items():
        if tier["instances"] is not None and macro in tier["macros"]:
            continue  # 非默认档里 KEY_1 等是真实通道宏（值 = 位置序），不核别名契约
        got = values.get(macro)
        if got is not None and got != expected:
            problems.append(
                f"{platform} 别名宏 {macro} 契约值 {expected}，实际 {got!r}"
            )
    known = set(tier["macros"]) | set(DEFAULT_ALIAS_MACROS)
    extras = set(values) - known
    if extras:
        problems.append(f"{platform} 出现未预期的通道宏：{sorted(extras)}")
    return problems


def _verify_single_instance_byte_identical(out: Path, platform: str) -> list[str]:
    """旧单实例：多实例渲染零写侧变化（泛型化后行为等价）。

    stm32：key_instances.h / pin_config.h 逐字节 = 母版默认；mspm0：库内默认
    key_instances.h 逐字节 + syscfg 未追加 KEY_<n> 输入实例（空计划不写）。
    """
    problems: list[str] = []
    if platform == PLATFORM_STM32:
        for label in ("key_instances.h", "pin_config.h"):
            src = LIB / "masters" / "stm32" / label
            dst = out / label
            if _norm(src.read_text(encoding="utf-8", errors="replace")) != _norm(
                dst.read_text(encoding="utf-8", errors="replace")
            ):
                problems.append(f"{platform} {label} 逐字节不写被破坏")
    else:
        src = MODULES / "key" / "code" / "key_instances.h"
        dst = out / "modules" / "key" / "code" / "key_instances.h"
        if _norm(src.read_text(encoding="utf-8", errors="replace")) != _norm(
            dst.read_text(encoding="utf-8", errors="replace")
        ):
            problems.append("mspm0 key_instances.h 逐字节不写被破坏")
        syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*const\s+KEY_[2-9]\d*\s*=\s*GPIO\.addInstance", syscfg, re.M):
            problems.append("mspm0 syscfg 被多实例渲染追加了 KEY_<n> 实例（空计划不该写）")
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


HEADER_NAME = "key_instances.h"


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
                    manifests=[KEY],
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

            if platform == PLATFORM_STM32:
                header_path = out / HEADER_NAME
            else:
                header_path = out / "modules" / "key" / "code" / HEADER_NAME
            header = header_path.read_text(encoding="utf-8", errors="replace")
            (tier_dir / HEADER_NAME).write_text(header, encoding="utf-8", errors="replace")
            problems += _verify_header(tier, header, platform)
            if tier["instances"] is None:
                problems += _verify_single_instance_byte_identical(out, platform)

            log = collect_build_log(
                platform,
                out,
                uv4=uv4 if platform == PLATFORM_STM32 else None,
                make=make if platform == PLATFORM_MSPM0 else None,
                timeout=300,
            )
            output = log.run.output or ""
            (tier_dir / "build.log").write_text(output, encoding="utf-8", errors="replace")
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
        "# key-multi-instance 双平台编译矩阵结果（工单 07）\n",
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
