# -*- coding: utf-8 -*-
"""wiki-materials 模块编译矩阵：对指定模块（或全部新模块）做 mspm0 单选真编译。

照 .scratch/module-polish/compile_matrix.py 配方：
resolve_selection(单选) → generate(带 ccs_tools) → collect_build_log(gmake)
→ compile_passed 判定 → 0 error 硬门槛 + 模块自身 warning 0。
用法：python .scratch/wiki-materials/compile_matrix.py [slug ...]
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
)
from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

HERE = Path(__file__).parent
LIB = REPO / "library"
OUT = HERE / "matrix"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
MAIN_C = "int main(void) { while (1); }\n"
BASELINE_WARNING_MARKERS = ("ovsRate", "higher oversampling rate")


def warning_failures(output: str) -> list[str]:
    return [
        line for line in output.splitlines()
        if line.lower().startswith(("warning", "warning:"))
        and not any(m.lower() in line.lower() for m in BASELINE_WARNING_MARKERS)
    ]


def main() -> int:
    slugs = sys.argv[1:] or ["ws2812", "hx711", "aht10", "sr04"]
    ccs = find_ccs_tools()
    make = find_make(GMAKE)
    if ccs is None or make is None:
        print(f"tools missing ccs={ccs} make={make}")
        return 2
    if OUT.exists():
        shutil.rmtree(OUT)
    results = []
    for slug in slugs:
        out = OUT / slug
        try:
            resolved = resolve_selection(LIB / "modules", PLATFORM_MSPM0, [slug])
            generate(
                platform=PLATFORM_MSPM0,
                manifests=resolved.manifests,
                module_library_dir=LIB / "modules",
                master_project_dir=LIB / "masters" / PLATFORM_MSPM0,
                output_dir=out,
                main_c_content=MAIN_C,
                ccs_tools=ccs,
            )
            log = collect_build_log(PLATFORM_MSPM0, out, make=make, timeout=300)
        except Exception as exc:  # noqa: BLE001
            results.append((slug, "GEN_FAIL", f"生成/编译异常:{exc}"))
            print(f"[FAIL-GEN] {slug}: {exc}")
            continue
        output = log.run.output or ""
        (out / "build.log").write_text(output, encoding="utf-8", errors="replace")
        ok = compile_passed(PLATFORM_MSPM0, log.run.exit_code) is True
        warns = warning_failures(output)
        errors = re.findall(r"\b(\d+)\s+error", output, re.I) or ["0"]
        result = "PASS" if ok and not warns else ("WARN_FAIL" if ok else "ERROR")
        results.append((slug, result, f"exit={log.run.exit_code} errors={errors[-1]} warnings={len(warns)}"))
        print(f"[{result}] {slug}: exit={log.run.exit_code} errors={errors[-1]} module_warnings={len(warns)}")
    return 0 if all(r[1] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
