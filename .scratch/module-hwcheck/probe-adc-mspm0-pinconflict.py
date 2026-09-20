# -*- coding: utf-8 -*-
"""探针：mspm0 上「选 adc 族模块」到底能不能生成工程（PA22 冲突是不是 adc 独有）。

本探针只回答一个问题：`adc` 那格 400「PA22 冲突」是**配方的问题**、还是
**母版 syscfg 的既有事实**（ADC12_0 把 8 个 MEM 脚全占了，其中 MEM6 = PA22 =
DEBUG_UART RX / OLED_SPI_RES）。取证方式：拿几个同样只声明了 ADC_CH0（= MEM0 /
PA24）的兄弟件跑同一发 /api/hwcheck/generate，看它们是不是同样 400。

用法：python .scratch/module-hwcheck/probe-adc-mspm0-pinconflict.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

# (器件, 串口, OLED)——adc 与它的兄弟件都只声明 ADC_CH0 = PA24
CASES: tuple[tuple[str, bool, bool], ...] = (
    ("adc", True, False),
    ("adc", False, True),
    ("adc", False, False),
    ("us016", True, False),
    ("mq2", True, False),
    ("photoresistance", True, False),
    ("ir_distance", True, False),
    ("flame", True, False),
)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    root = Path(tempfile.mkdtemp(prefix="firstep-probe-adcpin-"))
    ctx = AppContext(
        config_path=root / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=REPO / "library" / "modules",
            masters_dir=REPO / "library" / "masters",
        ),
        desktop_dir=lambda: root,
    )
    client = TestClient(create_app(ctx))
    for slug, uart, oled in CASES:
        response = client.post(
            "/api/hwcheck/generate",
            json={"platform": "mspm0", "debug_uart": uart, "oled": oled,
                  "devices": [slug], "parent_dir": str(root)},
        )
        tag = f"{slug:16s} uart={int(uart)} oled={int(oled)}"
        if response.status_code == 200:
            print(f"{tag} -> 200 OK")
            continue
        detail = str(response.json().get("detail", ""))
        head = detail.splitlines()[0] if detail else ""
        conflict = next((ln for ln in detail.splitlines()
                         if ln.strip().startswith("·")), "")
        print(f"{tag} -> {response.status_code} {head[:70]}")
        if conflict:
            print(f"{'':42s}   {conflict.strip()[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
