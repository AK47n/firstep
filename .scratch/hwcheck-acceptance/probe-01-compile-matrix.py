# -*- coding: utf-8 -*-
"""工单 hwcheck-acceptance/01 的真编译矩阵：**三条路**各至少一格 mspm0 真编译
0 error / 0 warning，stm32 抽一格不回归。

为什么必须有这一格：本单改的是 **mspm0 的 main.c 里那一行 SysConfig 初始化**
——从"注释占位"变成**活调用**。文档与文本断言只能证明"写进去了"，写进去的
东西真能不能编过（声明在不在、顺序对不对、有没有跟生成的头对不上）只有真
工具链说了算。判据是 `compile_passed` + 诊断计数（0 error / 0 warning）。

矩阵四格：

* **① 骨架式**（`generate_skeleton`，FakeLLM 出稿 → sanitize → 补行）：
  main.c 由骨架管线产出，含活 `SYSCFG_DL_init();`；
* **② 赛题式**（手写赛题式 main.c → `generate_project` 全链落盘）；
* **③ 检测程序**（`/api/hwcheck/generate` 端点，真库真母版）；
* **④ stm32 不回归**（UV4 真编译一格）。

用法：
    python .scratch/hwcheck-acceptance/probe-01-compile-matrix.py
读数落 `probe-01-compile-matrix.txt`（先落盘再打印）；**编译产物落系统临时
目录**（一份就近千个文件，跑完即清）——工作树只多这一个读数文件。
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
# 编译产物（母版整树 + 模块源码 + Debug/ 构建中间物，一份就近千个文件）落
# **系统临时目录**：本单的读数只有 `probe-01-compile-matrix.txt` 一个，产物
# 留在工作树里只会把 git status 淹掉（既有探针把产物放 .scratch/ 下，但那些
# 目录在 .gitignore 里；本目录没有，故不跟）。判据与读数完全一样——产物在哪
# 不影响编译器说什么。
BASE = Path(tempfile.mkdtemp(prefix="firstep-probe01-matrix-"))
REPORT = REPO / ".scratch" / "hwcheck-acceptance" / "probe-01-compile-matrix.txt"

# 骨架出稿：**故意只写模块初始化，不写 SYSCFG_DL_init**——补行那一道必须
# 自己把它补上（本单的确定性保证），编译过 = 补出来的那一行真的能编。
SKELETON_DRAFT = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "debug_uart_mspm0.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "  debug_uart_init();\n"
    "  DEBUG_PRINTF(\"bring-up\\r\\n\");\n"
    "  while (1) { }\n"
    "}\n"
)

# 赛题式出稿：学生真正拿到的那一版形态（模块调用 + 轮询循环）
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

# 诊断计数：只认编译器诊断行（`error:` / `warning:`），不数工具链收尾汇总
# （Keil 的 `0 Error(s), 0 Warning(s).` 自己含 Warning 子串，按行数会把 0 读成 1
# —— local-environment.md 记过这条）。
_DIAG_RE = re.compile(r"\b(error|warning)\b\s*[:#]", re.IGNORECASE)
_SUMMARY_RE = re.compile(r"^\d+\s+Error\(s\)")


def count_diagnostics(text: str) -> tuple[int, int]:
    """(错误数, 告警数)。只数诊断行；Keil 收尾汇总行排除。"""
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


def main() -> int:
    uv4 = find_uv4()
    make = find_make(GMAKE)
    ccs = find_ccs_tools()
    lines: list[str] = [
        "=== 工单 01 编译矩阵（三条路 + stm32 不回归）===",
        f"UV4：{uv4}",
        f"gmake：{make}",
        f"CCS 三件套：{ccs}",
        "",
        "判据：每一格 `compile_passed` 且 error = warning = 0；"
        "并对 mspm0 的产物 main.c 做**词法级**活调用核对（剥注释后仍有 "
        "`SYSCFG_DL_init();`，且只出现一次）。",
        "",
    ]
    failures: list[str] = []
    work = Path(tempfile.mkdtemp(prefix="firstep-probe01-"))
    try:
        # ---- ① 骨架式：generate_skeleton（FakeLLM 出稿 + sanitize + 补行）--
        label = "A-skeleton-mspm0"
        manifests = resolve_selection(
            MODULES, PLATFORM_MSPM0, ["led", "delay", "debug_uart"]
        ).manifests
        main_c, blocked = generate_skeleton(
            FakeLLM(main_skeleton=SKELETON_DRAFT),
            "温湿度采集与显示（编译矩阵用）",
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

        # ---- ② 赛题式：手写赛题 main.c → generate_project 全链 -------------
        label = "B-contest-mspm0"
        _compile(
            lines, failures, label, PLATFORM_MSPM0, ("led", "delay", "debug_uart"),
            CONTEST_MAIN, work, make=make, uv4=uv4,
        )

        # ---- ③ 检测程序：/api/hwcheck/generate 端点 ------------------------
        label = "C-hwcheck-mspm0"
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
        client = TestClient(create_app(ctx))
        response = client.post(
            "/api/hwcheck/generate",
            json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": True,
                  "parent_dir": str(work)},
        )
        if response.status_code != 200:
            lines.append(f"[检测程序] 生成失败 {response.status_code}："
                         f"{response.text[:160]}")
            failures.append(label)
        else:
            body = response.json()
            project = Path(body["output_dir"])
            live = _live_code(body["main_c"])
            lines.append(
                f"[检测程序] 端点生成 200、通道=串口+OLED（默认形态，PA22 自动让位）、"
                f"活调用 = {'SYSCFG_DL_init();' in live}"
            )
            _build_and_report(
                lines, failures, label, PLATFORM_MSPM0, project,
                main_c=body["main_c"], make=make, uv4=uv4,
            )

        # ---- ④ stm32 不回归：UV4 真编译一格 -------------------------------
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
        REPORT.write_text(report, encoding="utf-8")   # 先落盘
        print(report)
        return 1 if failures else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(BASE, ignore_errors=True)


def _live_code(code: str) -> str:
    """剥注释与字符串后的代码（词法判据与产品侧 clex 同源）。"""
    from contest_generator.clex import strip_comments

    return strip_comments(code)


def _compile(
    lines: list[str],
    failures: list[str],
    label: str,
    platform: str,
    slugs: tuple[str, ...],
    main_c: str,
    work: Path,
    *,
    make: Path | None,
    uv4: Path | None,
) -> None:
    """按给定 main.c 生成一格工程（mspm0 走 generate_project，stm32 同）。"""
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
        lines, failures, label, platform, out, main_c=main_c,
        make=make, uv4=uv4,
    )


def _build_and_report(
    lines: list[str],
    failures: list[str],
    label: str,
    platform: str,
    project: Path,
    *,
    main_c: str,
    make: Path | None,
    uv4: Path | None,
) -> None:
    """真编译一格并记读数（mspm0 另核对产物 main.c 的活调用）。"""
    on_disk = (project / "main.c").read_text(encoding="utf-8", errors="replace")
    live = _live_code(on_disk)
    count = live.count("SYSCFG_DL_init();")
    if platform == PLATFORM_MSPM0:
        if count != 1:
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
