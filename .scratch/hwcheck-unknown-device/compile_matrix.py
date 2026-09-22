# -*- coding: utf-8 -*-
"""hwcheck-unknown-device/01 编译矩阵：i2c_probe × 两平台 = 两组真编译。

每组：单选生成 → 平台编译（mspm0 = CCS Tools SysConfig CLI + gmake；
stm32 = UV4）→ 判定 0 error / 0 module warning。**产物与日志两分**：生成 + 编译
产物（几 MB 工程树，可重建）落 `matrix/`（按既有惯例 gitignore），逐组原始日志
落 `matrix-logs/` 入库当证据（照 `.scratch/magnetometer-modules/compile_matrix.py`
与 `matrix-logs/` 的先例）。

**本件两平台都是「借总线」的形态，编译矩阵要多证一件事**：stm32 侧生成出的
工程里 `i2c_probe_stm32.c` 真的被 uvprojx 收进编译单元、`pin_config.h` 里那四个
宏真的在；mspm0 侧 `I2C_0` 实例真的活着（`I2C_0_INST` 存在），否则
`i2c_probe.c` 直接编不过（这正是工单反证项要证明的那条链）。

用法：python .scratch/hwcheck-unknown-device/compile_matrix.py
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
# 生成 + 编译产物（几 MB 的工程树）落 matrix/——按既有惯例 gitignore；
# 逐组原始日志落 matrix-logs/ 入库当证据（magnetometer-modules 同款两分）。
MATRIX_DIR = REPO / ".scratch" / "hwcheck-unknown-device" / "matrix"
LOG_DIR = REPO / ".scratch" / "hwcheck-unknown-device" / "matrix-logs"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"

# main.c 只调本模块读侧三件事（同时证明「生成门禁认这三个函数」——mspm0 上
# main.c 只准调所选模块头里真实存在的函数）
MAIN_C = {
    "mspm0": (
        '#include "ti_msp_dl_config.h"\n'
        '#include "i2c_probe.h"\n'
        "\n"
        "int main(void)\n"
        "{\n"
        "    uint8_t value = 0u;\n"
        "    uint8_t got = 0u;\n"
        "    i2c_probe_init();\n"
        "    got = i2c_probe_ping(0x68u);\n"
        "    got = i2c_probe_read_reg(0x68u, 0x75u, &value);\n"
        "    (void)got;\n"
        "    (void)value;\n"
        "    while (1)\n"
        "    {\n"
        "    }\n"
        "}\n"
    ),
    "stm32": (
        '#include "headfile.h"\n'
        '#include "i2c_probe_stm32.h"\n'
        "\n"
        "int main(void)\n"
        "{\n"
        "    uint8_t value = 0u;\n"
        "    i2c_probe_init();\n"
        "    (void)i2c_probe_ping(0x68u);\n"
        "    (void)i2c_probe_read_reg(0x68u, 0x75u, &value);\n"
        "    (void)value;\n"
        "    while (1)\n"
        "    {\n"
        "    }\n"
        "}\n"
    ),
}


def run_one(platform: str) -> bool:
    plat = PLATFORM_MSPM0 if platform == "mspm0" else PLATFORM_STM32
    out = MATRIX_DIR / f"i2c_probe-{platform}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    resolved = resolve_selection(MODULES, plat, ["i2c_probe"])
    generate(
        platform=plat,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=REPO / "library" / "masters" / platform,
        output_dir=out,
        main_c_content=MAIN_C[platform],
        ccs_tools=find_ccs_tools() if platform == "mspm0" else None,
    )
    log = collect_build_log(
        plat, out,
        uv4=find_uv4() if platform == "stm32" else None,
        make=find_make(GMAKE) if platform == "mspm0" else None,
        timeout=600,
    )
    ok = compile_passed(plat, log.run.exit_code)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / f"i2c_probe-{platform}.log").write_text(
        f"exit_code={log.run.exit_code}\ncompile_passed={ok}\n\n{log.run.output}",
        encoding="utf-8",
    )
    # 警告面：排除工具自己的汇总行（`0 Error(s), 0 Warning(s).` 也含 "warning"
    # 子串，不排掉会把 0 警告读成 1 条——本单第一版就是这么误报的）。
    warnings = [
        line for line in log.run.output.splitlines()
        if "warning" in line.lower() and "warning(s)" not in line.lower()
    ]
    print(f"[i2c_probe/{platform}] exit={log.run.exit_code} passed={ok} "
          f"warnings={len(warnings)}")
    for w in warnings[:10]:
        print("    ", w.strip()[:160])
    return ok


def main() -> int:
    results = {}
    for platform in ("mspm0", "stm32"):
        try:
            results[platform] = run_one(platform)
        except Exception as exc:  # 生成期失败也算未通过，如实记录
            results[platform] = False
            print(f"[i2c_probe/{platform}] 异常：{type(exc).__name__}: {exc}")
    print("\n=== 矩阵结果 ===")
    for platform, ok in results.items():
        print(f"  i2c_probe {platform:6s} {'PASS' if ok else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
