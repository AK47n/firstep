"""module-polish/04 全库编译矩阵：逐模块 × 已有平台真编译。

产物：
- .scratch/module-polish/matrix_results.md  摘要
- .scratch/module-polish/matrix/*.log       逐条原始日志
只编译，不自动改 manifest；verified/notes 由后续 patch 按结果刷新。
"""
from __future__ import annotations

import json
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
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

HERE = Path(__file__).parent
LIB = REPO / "library"
MATRIX = HERE / "matrix"
RESULTS = HERE / "matrix_results.md"

GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
MAIN_C = "int main(void) { while (1); }\n"

BASELINE_WARNING_MARKERS = (
    "ovsRate",
    "higher oversampling rate",
)


def load_modules() -> list[dict]:
    out = []
    for d in sorted((LIB / "modules").iterdir()):
        if d.is_dir():
            data = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            data["_dir"] = d
            out.append(data)
    return out


def warning_failures(platform: str, output: str) -> list[str]:
    """非基线 warning 行（0 error 前提下）。"""
    if platform == PLATFORM_STM32:
        lines = [
            line for line in output.splitlines()
            if re.search(r"warning|Warning", line)
        ]
    else:
        # gmake 的 sysconfig/编译器 warning 行都以 warning: 开头
        lines = [
            line for line in output.splitlines()
            if line.lower().startswith(("warning", "warning:"))
        ]
    return [
        line for line in lines
        if not any(marker.lower() in line.lower() for marker in BASELINE_WARNING_MARKERS)
    ]


def main() -> int:
    modules = load_modules()
    uv4 = find_uv4()
    ccs = find_ccs_tools()
    make = find_make(GMAKE)
    if uv4 is None or ccs is None or make is None:
        print(f"tools missing uv4={uv4} ccs={ccs} make={make}")
        return 2

    if MATRIX.exists():
        shutil.rmtree(MATRIX)
    MATRIX.mkdir(parents=True)

    results: list[dict] = []
    for m in modules:
        slug = m["slug"]
        for platform in sorted(m["platforms"]):
            out = MATRIX / platform / slug
            try:
                resolved = resolve_selection(LIB / "modules", platform, [slug])
                generate(
                    platform=platform,
                    manifests=resolved.manifests,
                    module_library_dir=LIB / "modules",
                    master_project_dir=LIB / "masters" / platform,
                    output_dir=out,
                    main_c_content=MAIN_C,
                    ccs_tools=ccs if platform == PLATFORM_MSPM0 else None,
                )
                log = collect_build_log(
                    platform,
                    out,
                    uv4=uv4 if platform == PLATFORM_STM32 else None,
                    make=make if platform == PLATFORM_MSPM0 else None,
                    timeout=300,
                )
            except Exception as exc:  # noqa: BLE001
                results.append({
                    "slug": slug,
                    "platform": platform,
                    "exit": None,
                    "ok": False,
                    "errors": [],
                    "note": f"生成/编译异常：{exc}",
                })
                print(f"[FAIL-GEN] {slug}/{platform}: {exc}")
                continue

            output = log.run.output or ""
            (MATRIX / platform / slug).mkdir(parents=True, exist_ok=True)
            (MATRIX / platform / slug / "build.log").write_text(
                output, encoding="utf-8", errors="replace"
            )
            ok = compile_passed(platform, log.run.exit_code) is True
            warnings = warning_failures(platform, output)
            module_warnings_clean = not warnings
            errors = re.findall(r"\b(\d+)\s+error", output, re.I) or ["0"]
            results.append({
                "slug": slug,
                "platform": platform,
                "exit": log.run.exit_code,
                "ok": ok and module_warnings_clean,
                "errors": errors[-1],
                "warnings": warnings,
                "note": "",
            })
            print(
                f"[{'OK' if ok and module_warnings_clean else 'FAIL'}] {slug}/{platform} "
                f"exit={log.run.exit_code} errors={errors[-1]} module_warnings={len(warnings)}"
            )

    lines = [
        "# module-polish 编译矩阵结果\n",
        f"| slug | platform | exit | errors | 判定 | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        if r["ok"]:
            verdict = "PASS"
        elif r["exit"] is None:
            verdict = "GEN_FAIL"
        else:
            verdict = "WARN_FAIL" if r["exit"] in (0, 1) else "ERROR"
        note = r["note"] or (
            "非基线 warning: " + ("; ".join(r["warnings"][:3]) if r["warnings"] else "-")
        )
        lines.append(
            f"| {r['slug']} | {r['platform']} | {r['exit']} | {r['errors']} | {verdict} | {note} |"
        )
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"results: {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
