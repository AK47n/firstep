"""b1-adc-servo/03 双平台编译矩阵验收：adc + servo 生成工程在两条平台线
真机编译 0 error 0 warning，含引脚绑定场景；产物树跑生产门禁（同闸）。

用法：python .scratch/b1-adc-servo/compile_matrix.py
依赖：UV4（stm32）+ gmake/CCS 三件套（mspm0）可探测；真实库 + 真实母版。
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import (
    CcsTools,
    collect_build_log,
    compile_passed,
    find_ccs_tools,
    find_make,
    find_uv4,
    resolve_compile_toolchain,
)
from contest_generator.fix_errors import parse_compile_errors, summarize_compile_output
from contest_generator.generator import (
    build_output_tree_corpus,
    generate_project,
    run_generation_gates,
)
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32

OUT_ROOT = Path(__file__).parent / "out_matrix"

STM32_MAIN = (
    '#include "stm32f10x.h"\n'
    '#include "headfile.h"\n'
    '#include "servo.h"\n'
    "int main(void) {\n"
    "    SystemInit();\n"
    "    adc_init(ADC_1, ADC_Channel_0);\n"
    "    servo_init(1);\n"
    "    servo_set_angle(1, 90);\n"
    "    while (1) {}\n"
    "}\n"
)

MSPM0_MAIN = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "adc_mspm0.h"\n'
    '#include "servo.h"\n'
    "int main(void) {\n"
    "    /* TODO: 若使用 SysConfig 生成的外设初始化，请取消下面注释 */\n"
    "    // SYSCFG_DL_init();\n"
    "    adc_init(ADC_1, ADC_Channel_0);\n"
    "    servo_init(1);\n"
    "    servo_set_angle(1, 90);\n"
    "    while (1) {}\n"
    "}\n"
)


def run_case(platform: str, name: str, bindings=None) -> None:
    out_dir = OUT_ROOT / f"{name}_{platform}"
    ccs_tools: CcsTools | None = None
    if platform == PLATFORM_MSPM0:
        ccs_tools = find_ccs_tools("", "", "")
        if ccs_tools is None:
            raise AssertionError("[mspm0] 未探测到 CCS 三件套，跳过（环境缺件）")
    summary = generate_project(
        platform=platform,
        slugs=["adc", "servo"],
        main_c_content=MSPM0_MAIN if platform == PLATFORM_MSPM0 else STM32_MAIN,
        output_dir=out_dir,
        module_library_dir=REPO / "library" / "modules",
        masters_dir=REPO / "library" / "masters",
        bindings=bindings,
        ccs_tools=ccs_tools,
    )
    # 门禁同闸：产物树重建语料跑生产 run_generation_gates
    if platform == PLATFORM_STM32:
        search_dirs = _uvprojx_include_dirs(out_dir)
    else:
        search_dirs = _cproject_include_dirs(out_dir)
    corpus = build_output_tree_corpus(out_dir, platform, search_dirs)
    try:
        run_generation_gates(corpus, [], platform)
    except Exception as exc:  # noqa: BLE001 - 验收脚本把门禁失败当断言失败
        raise AssertionError(f"[{name}/{platform}] 生成门禁失败：{exc}") from exc

    uv4, make = resolve_compile_toolchain(platform, make_override=_gmake_override())
    build = collect_build_log(platform, out_dir, uv4=uv4, make=make)
    parsed = parse_compile_errors(build.run.output)
    summary = summarize_compile_output(build.run.output, parsed)
    passed = compile_passed(platform, build.run.exit_code)
    print(
        f"[{name}/{platform}] exit={build.run.exit_code} passed={passed} "
        f"errors={summary['errors']} warnings={summary['warnings']} "
        f"dur={build.run.duration:.1f}s"
    )
    if not passed:
        print(build.run.output[-3000:])
        raise AssertionError(f"[{name}/{platform}] 编译失败")
    if summary["errors"] or summary["warnings"]:
        print(build.run.output[-3000:])
        raise AssertionError(
            f"[{name}/{platform}] 0 错 0 警不满足：{summary}"
        )


def _gmake_override() -> str:
    """读用户 config.json 的 gmake_path（与 webapp 同源，缺省自动探测）。"""
    from contest_generator.config import load_config

    try:
        return load_config().gmake_path
    except Exception:  # noqa: BLE001 - 无 config 走自动探测
        return ""


def _uvprojx_include_dirs(out_dir: Path) -> list[Path]:
    """解析最终 .uvprojx 的 IncludePath（相对 .uvprojx 所在目录）→ 绝对路径
    （照 .scratch/real-run/generate_check.py 同款实现，门禁 search_dirs 语义）。"""
    import xml.etree.ElementTree as ET

    uvprojx = next(out_dir.rglob("*.uvprojx"), None)
    if uvprojx is None:
        return []
    dirs: list[Path] = []
    try:
        root = ET.parse(uvprojx).getroot()
    except ET.ParseError:
        return []
    for el in root.findall("Targets/Target"):
        path_el = el.find(
            "TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
        )
        if path_el is None or not path_el.text:
            continue
        for entry in path_el.text.split(";"):
            p = Path(entry.strip().replace("\\", "/"))
            if not entry.strip():
                continue
            resolved = p if p.is_absolute() else (uvprojx.parent / p)
            try:
                dirs.append(resolved.resolve())
            except OSError:
                continue
    return dirs


def _cproject_include_dirs(out_dir: Path) -> list[Path]:
    """解析最终 .cproject 的 IncludePath（CCS 语义，mspm0 线）→ 绝对路径。"""
    import xml.etree.ElementTree as ET

    cproject = next(out_dir.rglob(".cproject"), None)
    if cproject is None:
        return []
    dirs: list[Path] = []
    try:
        root = ET.parse(cproject).getroot()
    except ET.ParseError:
        return []
    for opt in root.iter("option"):
        if opt.get("valueType") != "includePath":
            continue
        for vo in opt.findall("listOptionValue"):
            val = (vo.get("value") or "").strip()
            if not val:
                continue
            p = Path(val.replace("${PROJECT_LOC}", str(cproject.parent))
                     .replace("${PROJECT_ROOT}", str(cproject.parent)))
            if "${" in str(p):
                continue
            try:
                dirs.append(p.resolve())
            except OSError:
                continue
    return dirs


if __name__ == "__main__":
    if OUT_ROOT.exists():
        import shutil

        shutil.rmtree(OUT_ROOT)
    # 默认脚
    run_case(PLATFORM_STM32, "default")
    run_case(PLATFORM_MSPM0, "default")
    # 绑定场景：stm32 adc→PA5、servo→PA0；mspm0 adc→PA26、servo→PA12
    run_case(
        PLATFORM_STM32,
        "bound",
        {"adc.ADC_CH0": "PA5", "servo.SERVO_PWM_C0": "PA0"},
    )
    run_case(
        PLATFORM_MSPM0,
        "bound",
        {"adc.ADC_CH0": "PA26", "servo.SERVO_PWM_C0": "PA12"},
    )
    print("编译矩阵全部通过：4 例 × 0 error 0 warning + 门禁同闸")
