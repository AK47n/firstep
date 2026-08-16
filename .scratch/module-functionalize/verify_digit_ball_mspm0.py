"""module-functionalize 批次真机编译脚本（mspm0）：digit+ball 共享 UART1 验收。

用法：python verify_digit_ball_mspm0.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import find_ccs_tools, find_make
from contest_generator.generator import generate
from contest_generator.platforms import PLATFORM_MSPM0
from contest_generator.selection import resolve_selection

GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"


def main() -> int:
    lib = REPO / "library"
    out = HERE / "out_digit_ball_mspm0"
    if out.exists():
        shutil.rmtree(out)

    tools = find_ccs_tools()
    if tools is None:
        print("CCS 工具链未探测到")
        return 2
    make = find_make(GMAKE)
    if make is None:
        print(f"gmake 未找到：{GMAKE}")
        return 2

    resolved = resolve_selection(lib / "modules", PLATFORM_MSPM0,
                                 ["digit_uart", "ball_detect"])
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=lib / "modules",
        master_project_dir=lib / "masters" / PLATFORM_MSPM0,
        output_dir=out,
        main_c_content=(HERE / "main_mspm0_digit_ball.c").read_text(encoding="utf-8"),
        ccs_tools=tools,
    )

    log = out / "gmake_build.log"
    proc = subprocess.run(
        [str(make), "-C", str(out / "Debug"), "-f", "makefile", "-B", "all"],
        capture_output=True, text=True, timeout=600,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    log.write_text(text, encoding="utf-8")
    tail = text.strip().splitlines()[-6:] if text.strip() else ["无输出"]
    print(f"[digit+ball gmake] exit={proc.returncode}")
    print("\n".join(tail))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
