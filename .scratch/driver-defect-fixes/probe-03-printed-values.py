# -*- coding: utf-8 -*-
"""量具：hx711 两格的读数**实际印成什么**（工单 `driver-defect-fixes/03` 的文案整改依据）。

review 指出配方文案写「页面印 4294967295」，而渲染出口是 `hwcheck_report_int(int)`、
`locals` 声明是 `uint32_t raw` ⇒ 0xFFFFFFFF 过 int 形参会印成 **-1**。本量具不猜：
真调 `/api/hwcheck/preview` 把两格的 `main.c` 拿回来，把读数行原文打出来。

用法：`py -3 .scratch/driver-defect-fixes/probe-03-printed-values.py`
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
REPORT = REPO / ".scratch" / "driver-defect-fixes" / "probe-03-printed-values.txt"


def main() -> int:
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app

    ctx = AppContext(
        config_path=Path(REPO) / ".scratch" / "_probe-cfg" / "config.json",
        config=AppConfig(api_key="sk-test", module_library_dir=MODULES, masters_dir=MASTERS),
        desktop_dir=lambda: REPO / ".scratch",
    )
    client = TestClient(create_app(ctx))
    rows: list[str] = ["=== hx711 两格的读数实际印成什么（判据：hwcheck_report_int 的形参类型）==="]
    for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
        payload = {"platform": platform, "debug_uart": True, "oled": False,
                   "devices": ["hx711"]}
        response = client.post("/api/hwcheck/preview", json=payload)
        rows.append(f"## {platform}  预览 HTTP {response.status_code}")
        if response.status_code != 200:
            rows.append("  " + str(response.text)[:200])
            continue
        main_c = response.json()["main_c"]
        rows.append("  读数段原文：")
        for line in main_c.splitlines():
            if "raw" in line and ("hwcheck_report" in line or "printf" in line):
                rows.append("    " + line.rstrip())
        for match in re.finditer(r"static void hwcheck_report_int[^\n]*\n(?:[^\n]*\n){0,12}", main_c):
            rows.append("  hwcheck_report_int 实现摘录：")
            rows += ["    " + ln for ln in match.group(0).splitlines()[:12]]
            break
        rows.append("")
    text = "\n".join(rows) + "\n"
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
