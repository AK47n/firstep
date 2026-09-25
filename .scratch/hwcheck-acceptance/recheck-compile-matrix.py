# -*- coding: utf-8 -*-
"""硬件检测复测（2026-09-25）：**真编译**三路 mspm0 工程 + stm32 不回归。

与原 `probe-01-compile-matrix.py` 的关系：**同一套判据、同一个工具链**，只在两处不同：
① 读数落本文件自己的 `recheck-compile-matrix.txt`（不覆盖工单 01 的原始读数）；
② 新增一格 **E**——`OLED 通道 + aht10` 走检测端点生成并真编译。这一格是原报告 §3
   点名"生成前必 400"的组合，只有它能证明"屏幕 + 我新买的那件 I2C 器件"这条路
   从**能生成**一直通到**能编译**。

判据：每格 `compile_passed` 且 error = warning = 0；mspm0 产物 main.c 剥注释后
`SYSCFG_DL_init();` 恰好 1 处（那行是活的，不是注释占位）。

用法：
    python .scratch/hwcheck-acceptance/recheck-compile-matrix.py
编译产物落系统临时目录，跑完即清；工作树只多一个读数文件。
"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log, compile_passed, find_ccs_tools, find_make, find_uv4,
)
from contest_generator.generator import generate_project  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402
from contest_generator.skeleton import generate_skeleton  # noqa: E402
from tests.fakes import FakeLLM  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
BASE = Path(tempfile.mkdtemp(prefix="firstep-recheck-matrix-"))
REPORT = REPO / ".scratch" / "hwcheck-acceptance" / "recheck-compile-matrix.txt"

SKELETON_DRAFT = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "debug_uart_mspm0.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "  debug_uart_init();\n"
    '  DEBUG_PRINTF("bring-up\\r\\n");\n'
    "  while (1) { }\n"
    "}\n"
)

CONTEST_MAIN = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "debug_uart_mspm0.h"\n'
    '#include "led.h"\n'
    '#include "delay.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    SYSCFG_DL_init();\n"
    "    debug_uart_init();\n"
    "    led_init(LED_RED);\n"
    "    while (1)\n"
    "    {\n"
    "        led_toggle(LED_RED);\n"
    "        delay_ms(500);\n"
    "    }\n"
    "}\n"
)

STM32_MAIN = (
    "#include \"headfile.h\"\n"
    "#include \"aht10_stm32.h\"\n"
    "\n"
    "int main(void)\n"
    "{\n"
    "    aht10_init();\n"
    "    float t = aht10_read_temperature();\n"
    "    (void)t;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

_DIAG_RE = re.compile(r"\b(error|warning)\b\s*[:#]", re.IGNORECASE)
_SUMMARY_RE = re.compile(r"^\d+\s+Error\(s\)")


def count_diagnostics(text: str) -> tuple[int, int]:
    errors = warnings = 0
    for line in text.splitlines():
        stripped = line.strip()
        if _SUMMARY_RE.match(stripped) or stripped.startswith("Build Time"):
            continue
        match = _DIAG_RE.search(stripped)
        if match is None:
            continue
        if match.group(1).lower() == "error":
            errors += 1
        else:
            warnings += 1
    return errors, warnings


def _live_code(code: str) -> str:
    from contest_generator.clex import strip_comments

    return strip_comments(code)


def _make_client(work: Path):
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app

    ctx = AppContext(
        config_path=work / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=MODULES,
            masters_dir=MASTERS,
        ),
        desktop_dir=lambda: work,
    )
    return TestClient(create_app(ctx))


def _hwcheck_cell(lines, failures, label, client, work, payload, *, make, uv4) -> None:
    """/api/hwcheck/generate 生成一格并真编译。"""
    response = client.post("/api/hwcheck/generate", json=payload)
    if response.status_code != 200:
        lines.append(f"[生成拦下] {label}：HTTP {response.status_code} —— "
                     f"{response.text[:200]}")
        failures.append(label)
        return
    body = response.json()
    project = Path(body["output_dir"])
    devices = body.get("devices") or []
    live = _live_code(body["main_c"])
    lines.append(
        f"[检测程序] {label}：端点生成 200、device={devices or '（无）'}、"
        f"oled={payload.get('oled', True)}、活调用 = {'SYSCFG_DL_init();' in live}"
    )
    _build_and_report(
        lines, failures, label, PLATFORM_MSPM0, project,
        main_c=body["main_c"], make=make, uv4=uv4,
    )


def main() -> int:
    uv4 = find_uv4()
    make = find_make(GMAKE)
    ccs = find_ccs_tools()
    lines: list[str] = [
        "=== 硬件检测复测：三路 mspm0 真编译 + stm32 不回归（2026-09-25）===",
        f"UV4：{uv4}",
        f"gmake：{make}",
        f"CCS 三件套：{ccs}",
        "",
        "判据：每一格 `compile_passed` 且 error = warning = 0；对 mspm0 产物 main.c 剥注释后",
        "核对活调用 `SYSCFG_DL_init();` 恰好 1 处（那一行必须是活的，不是注释占位）。",
        "",
    ]
    failures: list[str] = []
    work = Path(tempfile.mkdtemp(prefix="firstep-recheck-"))
    try:
        # ---- ① 骨架式 ------------------------------------------------------
        label = "A-skeleton-mspm0"
        manifests = resolve_selection(
            MODULES, PLATFORM_MSPM0, ["led", "delay", "debug_uart"]
        ).manifests
        main_c, blocked = generate_skeleton(
            FakeLLM(main_skeleton=SKELETON_DRAFT),
            "温湿度采集与显示（复测用）",
            manifests,
            PLATFORM_MSPM0,
            MODULES,
            MASTERS / "mspm0",
        )
        lines.append(
            f"[骨架式] generate_skeleton：blocked={blocked!r}、"
            f"补行后活调用 = {'SYSCFG_DL_init();' in _live_code(main_c)}"
        )
        _compile(
            lines, failures, label, PLATFORM_MSPM0, ("led", "delay", "debug_uart"),
            main_c, work, make=make, uv4=uv4,
        )

        # ---- ② 赛题式 ------------------------------------------------------
        label = "B-contest-mspm0"
        _compile(
            lines, failures, label, PLATFORM_MSPM0, ("led", "delay", "debug_uart"),
            CONTEST_MAIN, work, make=make, uv4=uv4,
        )

        # ---- ③ 检测程序（默认通道） ----------------------------------------
        client = _make_client(work)
        _hwcheck_cell(
            lines, failures, "C-hwcheck-mspm0-默认通道", client, work,
            {"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": True,
             "parent_dir": str(work)},
            make=make, uv4=uv4,
        )

        # ---- ④ 检测程序：OLED 通道 + 库内 I2C 器件（原报告点名必 400） -----
        _hwcheck_cell(
            lines, failures, "E-hwcheck-oled+aht10-mspm0", client, work,
            {"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": True,
             "devices": ["aht10"], "parent_dir": str(work)},
            make=make, uv4=uv4,
        )

        # ---- ⑤ 检测程序：OLED 通道 + 专精件 --------------------------------
        _hwcheck_cell(
            lines, failures, "F-hwcheck-oled+mpu6050-mspm0", client, work,
            {"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": True,
             "devices": ["ml_mpu6050"], "parent_dir": str(work)},
            make=make, uv4=uv4,
        )

        # ---- ⑥ stm32 不回归 ------------------------------------------------
        label = "D-stm32-no-regression"
        _compile(
            lines, failures, label, PLATFORM_STM32, ("aht10", "delay"),
            STM32_MAIN, work, make=None, uv4=uv4,
        )

        lines.append("")
        lines.append(
            "=== 结论：" + ("全绿（0 error / 0 warning）" if not failures
                            else "有 FAIL：" + "、".join(failures)) + " ==="
        )
        report = "\n".join(lines) + "\n"
        REPORT.write_text(report, encoding="utf-8")
        print(report)
        return 1 if failures else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(BASE, ignore_errors=True)


def _compile(lines, failures, label, platform, slugs, main_c, work, *, make, uv4) -> None:
    out = BASE / label
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    try:
        generate_project(
            platform=platform,
            slugs=list(slugs),
            main_c_content=main_c,
            output_dir=out,
            module_library_dir=MODULES,
            masters_dir=MASTERS,
            ccs_tools=find_ccs_tools() if platform == PLATFORM_MSPM0 else None,
        )
    except Exception as exc:  # noqa: BLE001 —— 证据脚本要结论不要栈
        lines.append(f"[生成拦下] {label}：{type(exc).__name__}")
        for detail in str(exc).splitlines()[:3]:
            lines.append("           " + detail.strip()[:150])
        failures.append(label)
        return
    _build_and_report(
        lines, failures, label, platform, out, main_c=main_c, make=make, uv4=uv4,
    )


def _build_and_report(lines, failures, label, platform, project, *, main_c, make, uv4) -> None:
    on_disk = (project / "main.c").read_text(encoding="utf-8", errors="replace")
    live = _live_code(on_disk)
    count = live.count("SYSCFG_DL_init();")
    if platform == PLATFORM_MSPM0 and count != 1:
        lines.append(f"           ⚠ 产物 main.c 的活调用计数 = {count}（应为 1）")
        failures.append(f"{label}:syscfg-init-count")
    log = collect_build_log(
        platform, project,
        make=make if platform == PLATFORM_MSPM0 else None,
        uv4=uv4 if platform == PLATFORM_STM32 else None,
        timeout=900,
    )
    text = log.run.output or ""
    errors, warnings = count_diagnostics(text)
    ok = compile_passed(platform, log.run.exit_code) and not errors and not warnings
    lines.append(
        f"[{'PASS' if ok else 'FAIL'}] {label}：exit={log.run.exit_code}、"
        f"error {errors}、warning {warnings}、产物 main.c 活调用 {count} 处"
    )
    if not ok:
        failures.append(label)
        for line in text.splitlines():
            if _DIAG_RE.search(line):
                lines.append("           " + line.strip()[:160])


if __name__ == "__main__":
    raise SystemExit(main())
