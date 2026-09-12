# -*- coding: utf-8 -*-
"""magnetometer-modules 编译矩阵（工单 04）：两件 × 两平台 = 四组真编译。

每组：单选生成 → 平台编译（mspm0 = SysConfig CLI + gmake；stm32 = UV4）
→ 0 error / 0 module warning 判定。原始输出逐组落盘到本目录 matrix/ 下供留档。

用法：python .scratch/magnetometer-modules/compile_matrix.py
"""
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log, compile_passed, find_ccs_tools, find_make, find_uv4,
)
from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MODULES = REPO / "library" / "modules"
MATRIX_DIR = REPO / ".scratch" / "magnetometer-modules" / "matrix"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"

# main.c 只调本模块 API（证明头文件与实现真能编成工程）
MAIN_C = {
    "hmc5883l": {
        "mspm0": (
            '#include "ti_msp_dl_config.h"\n'
            '#include "hmc5883l.h"\n'
            "int main(void) { int16_t x = 0, y = 0, z = 0; float deg = 0.0f;\n"
            "  uint8_t st = hmc5883l_init(); (void)st;\n"
            "  (void)hmc5883l_read(&x, &y, &z);\n"
            "  (void)hmc5883l_read_heading(&deg, 0, 0);\n"
            "  deg = hmc5883l_heading_from_xy((float)x, (float)y); (void)deg;\n"
            "  while (1) {} }\n"
        ),
        "stm32": (
            '#include "headfile.h"\n'
            '#include "hmc5883l_stm32.h"\n'
            "int main(void) { int16_t x = 0, y = 0, z = 0; float deg = 0.0f;\n"
            "  uint8_t st = hmc5883l_init(); (void)st;\n"
            "  (void)hmc5883l_read(&x, &y, &z);\n"
            "  (void)hmc5883l_read_heading(&deg, 0, 0);\n"
            "  while (1) {} }\n"
        ),
    },
    "qmc5883l": {
        "mspm0": (
            '#include "ti_msp_dl_config.h"\n'
            '#include "qmc5883l.h"\n'
            "int main(void) { int16_t x = 0, y = 0, z = 0; float deg = 0.0f;\n"
            "  uint8_t st = qmc5883l_init(); (void)st;\n"
            "  (void)qmc5883l_read(&x, &y, &z);\n"
            "  (void)qmc5883l_read_heading(&deg, 0, 0);\n"
            "  while (1) {} }\n"
        ),
        "stm32": (
            '#include "headfile.h"\n'
            '#include "qmc5883l_stm32.h"\n'
            "int main(void) { int16_t x = 0, y = 0, z = 0; float deg = 0.0f;\n"
            "  uint8_t st = qmc5883l_init(); (void)st;\n"
            "  (void)qmc5883l_read(&x, &y, &z);\n"
            "  (void)qmc5883l_read_heading(&deg, 0, 0);\n"
            "  while (1) {} }\n"
        ),
    },
}

PLATFORM_DIR = {"mspm0": "mspm0", "stm32": "stm32"}


def run_one(slug: str, platform: str) -> bool:
    plat = PLATFORM_MSPM0 if platform == "mspm0" else PLATFORM_STM32
    out = MATRIX_DIR / f"{slug}-{platform}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    resolved = resolve_selection(MODULES, plat, [slug])
    generate(
        platform=plat,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=REPO / "library" / "masters" / PLATFORM_DIR[platform],
        output_dir=out,
        main_c_content=MAIN_C[slug][platform],
        ccs_tools=find_ccs_tools() if platform == "mspm0" else None,
    )
    log = collect_build_log(
        plat, out,
        uv4=find_uv4() if platform == "stm32" else None,
        make=find_make(GMAKE) if platform == "mspm0" else None,
        timeout=600,
    )
    ok = compile_passed(plat, log.run.exit_code)
    (MATRIX_DIR / f"{slug}-{platform}.log").write_text(
        f"exit_code={log.run.exit_code}\ncompile_passed={ok}\n\n{log.run.output}",
        encoding="utf-8",
    )
    # 警告面：模块自身文件的 warning（硬门槛 = 0 module warning）
    warnings = [
        line for line in log.run.output.splitlines()
        if "warning" in line.lower() and slug in line
    ]
    print(f"[{slug}/{platform}] exit={log.run.exit_code} passed={ok} "
          f"module_warnings={len(warnings)}")
    for w in warnings[:10]:
        print("    ", w.strip()[:160])
    return ok and not warnings


def main() -> int:
    results = {}
    for slug in ("hmc5883l", "qmc5883l"):
        for platform in ("mspm0", "stm32"):
            try:
                results[(slug, platform)] = run_one(slug, platform)
            except Exception as exc:  # 生成期失败也算未通过，如实记录
                results[(slug, platform)] = False
                print(f"[{slug}/{platform}] 异常：{type(exc).__name__}: {exc}")
    print("\n=== 矩阵结果 ===")
    for (slug, platform), ok in results.items():
        print(f"  {slug:10s} {platform:6s} {'PASS' if ok else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
