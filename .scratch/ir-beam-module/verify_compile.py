"""ir-beam-module/01 编译验收：ir_beam 双平台单选生成 + 真编译。

复用 module-polish/compile_matrix.py 既定配方（generate → collect_build_log →
compile_passed）；只编 ir_beam 单模块。产物写入 .scratch/ir-beam-module/
verify_out/<platform>/。
"""

from __future__ import annotations

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
OUT = HERE / "verify_out"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
MAIN_C = "int main(void) { while (1); }\n"


def main() -> int:
    uv4 = find_uv4()
    ccs = find_ccs_tools()
    make = find_make(GMAKE)
    print(f"tools: uv4={uv4} ccs={ccs is not None} make={make}")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
        slug = "ir_beam"
        out = OUT / platform / slug
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
        output = log.run.output or ""
        (out / "build.log").write_text(output, encoding="utf-8", errors="replace")
        ok = compile_passed(platform, log.run.exit_code) is True
        print(f"[{'OK' if ok else 'FAIL'}] {slug}/{platform} exit={log.run.exit_code}")
        if not ok:
            print(output[-4000:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
