# -*- coding: utf-8 -*-
"""复测插曲：`.sysmem` 链接告警（#10210-D）到底由谁带出来。

起因：本轮真编译矩阵新增的一格 `OLED 通道 + ml_mpu6050` 编译**通过**（exit=0、0 error）
但带 1 条 `warning #10210-D: creating ".sysmem" section ...`，与"这批工程 0 warning"
的验收线不符。既有批次（`.scratch/hwcheck-unknown-device/probe-*-compile-matrix.txt`）
把同一条告警标成**「已知工具链」**（自建件探测用 stdio 时出现），所以先量清楚：
这一格是"已知工具链告警的又一次出现"，还是"OLED + 传感器这个新解开组合独有"。

量法：五格全部走 `/api/hwcheck/generate` + gmake 真编译，**同一轮**里互相做对照：
  1. oled-only      （基线：不选器件、开 OLED）
  2. mpu6050-无OLED  （同一件器件、关掉 OLED 通道）
  3. mpu6050-带OLED  （本轮报出的那一格）
  4. jy61p-带OLED    （换一件专精件，看是不是 mpu6050 独有）
  5. aht10-带OLED    （未专精件，已知那一格无告警）

用法：`python .scratch/hwcheck-acceptance/recheck-isolate-sysmem.py`
读数落 `recheck-isolate-sysmem.txt`。
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
    collect_build_log, compile_passed, find_ccs_tools, find_make,
)
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
REPORT = REPO / ".scratch" / "hwcheck-acceptance" / "recheck-isolate-sysmem.txt"

BASE = Path(tempfile.mkdtemp(prefix="firstep-recheck-sysmem-"))

CELLS = [
    ("1-oled-only", [], True),
    ("2-mpu6050-无OLED", ["ml_mpu6050"], False),
    ("3-mpu6050-带OLED", ["ml_mpu6050"], True),
    ("4-jy61p-带OLED", ["jy61p"], True),
    ("5-aht10-带OLED", ["aht10"], True),
]

_DIAG_RE = re.compile(r"\b(error|warning)\b\s*[:#]", re.IGNORECASE)
_SUMMARY_RE = re.compile(r"^\d+\s+Error\(s\)")


def count_diagnostics(text: str) -> tuple[int, int]:
    errors = warnings = 0
    for line in text.splitlines():
        stripped = line.strip()
        if _SUMMARY_RE.match(stripped) or stripped.startswith("Build Time"):
            continue
        m = _DIAG_RE.search(stripped)
        if m is None:
            continue
        if m.group(1).lower() == "error":
            errors += 1
        else:
            warnings += 1
    return errors, warnings


def main() -> int:
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app

    make = find_make(GMAKE)
    lines = [
        "=== 复测插曲：`.sysmem` 告警（#10210-D）隔离测量 ===",
        f"gmake：{make}",
        f"CCS 三件套：{find_ccs_tools()}",
        "",
        "判据：先看每格的 error / warning 计数，再看告警原文归谁。",
        "",
    ]
    work = Path(tempfile.mkdtemp(prefix="firstep-recheck-sysmem-work-"))
    try:
        ctx = AppContext(
            config_path=work / "cfg" / "config.json",
            config=AppConfig(api_key="sk-test", module_library_dir=MODULES,
                             masters_dir=MASTERS),
            desktop_dir=lambda: work,
        )
        client = TestClient(create_app(ctx))
        for label, devices, oled in CELLS:
            payload = {"platform": PLATFORM_MSPM0, "debug_uart": True,
                       "oled": oled, "parent_dir": str(work)}
            if devices:
                payload["devices"] = devices
            response = client.post("/api/hwcheck/generate", json=payload)
            if response.status_code != 200:
                lines.append(f"[拦下] {label}：HTTP {response.status_code} "
                             f"{response.text[:120]}")
                continue
            project = Path(response.json()["output_dir"])
            log = collect_build_log(PLATFORM_MSPM0, project, make=make, timeout=900)
            text = log.run.output or ""
            errors, warnings = count_diagnostics(text)
            ok = compile_passed(PLATFORM_MSPM0, log.run.exit_code) and not errors
            lines.append(
                f"[{'PASS' if ok else 'FAIL'}] {label}（器件={devices or '无'}、"
                f"OLED={oled}）：exit={log.run.exit_code}、error {errors}、"
                f"warning {warnings}"
            )
            if warnings:
                for line in text.splitlines():
                    if _DIAG_RE.search(line):
                        lines.append("        " + line.strip()[:170])
        lines.append("")
        report = "\n".join(lines) + "\n"
        REPORT.write_text(report, encoding="utf-8")
        print(report)
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(BASE, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
