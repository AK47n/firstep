# -*- coding: utf-8 -*-
"""工单 module-hwcheck/07 的编译矩阵探针（stm32 UV4 + mspm0 gmake 真编译）。

用法：python .scratch/module-hwcheck/probe-07-compile-matrix.py

**为什么要单独一支**：本单让**未专精件**第一次进产物——三种从没编过的形态：

* 通用件的**无参初始化调用**（`sht20_init();` / `ws2812_init();`）；
* I2C 类件的**总线扫描**（`hwcheck_i2c_ping` 用 `GPIOn_enum` / `OUT_OD` / `IU`
  这些 ml_gpio 类型，参数 = manifest 声明的引脚宏）＋ 它必须带的
  `pin_config.h`（**headfile.h 不带这个头**——宿主机行为探针当时就报
  `SHT20_SCL_GPIO undeclared`，这就是本条真机判据的价值）；
* **认不出初始化**的件（`servo` 的 init 要参数）——那一节只打说明、不做动作，
  0 warning 的验收线要看它有没有留下没用的东西。

形态：**stm32 五形态 + mspm0 两形态**（mspm0 侧没有 pin_config 宏 → 无扫描，
如实编"只有初始化"那一路）。

判据：passed=True 且 error=warning=0。输出：probe-07-compile-matrix.txt +
probe-07-buildlogs/ 下的原始日志。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.compile_runner import (  # noqa: E402
    find_ccs_tools,
    find_make,
    find_uv4,
    run_compile,
)
from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.sse import SseEmitter  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe-07-compile-matrix.txt"
LOGS = HERE / "probe-07-buildlogs"

# (平台, 标签, 器件, 串口, OLED)
VARIANTS: tuple[tuple[str, str, tuple[str, ...], bool, bool], ...] = (
    ("stm32", "框架（不选器件：回归基线）", (), True, False),
    ("stm32", "beep 通用件（非 I2C：只有初始化）", ("beep",), True, False),
    ("stm32", "sht20 通用件（I2C：初始化 + 总线扫描 + pin_config.h）",
     ("sht20",), True, False),
    ("stm32", "servo 通用件（初始化要参数 → 这一节不做动作）",
     ("servo",), True, False),
    ("stm32", "led 专精 + sht20 通用（两套运行时同堂）",
     ("led", "sht20"), True, False),
    ("mspm0", "ws2812 通用件（非 I2C，无扫描）", ("ws2812",), True, False),
    ("mspm0", "aht10 通用件（mspm0 侧 I2C 角色无宏 → 不扫）",
     ("aht10",), True, False),
)


class _Collector(SseEmitter):
    """最小 SSE 收集器（run_compile 的 emit 缝）：只收事件名与载荷。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def progress(self, event) -> None:
        self.events.append(("progress", event.to_dict()
                            if hasattr(event, "to_dict") else {"type": str(event)}))

    def done(self, data: dict) -> None:
        self.events.append(("done", data))

    def error(self, data: dict) -> None:
        self.events.append(("error", data))

    def question(self, data: dict) -> None:
        self.events.append(("question", data))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    uv4 = find_uv4()
    make = find_make()
    ccs = find_ccs_tools()
    lines: list[str] = [
        "# 工单 module-hwcheck/07 编译矩阵（stm32 UV4 + mspm0 gmake 真编译）", "",
        f"UV4：{uv4}",
        f"gmake：{make}",
        f"CCS 三件套：{ccs}",
        "",
        "形态（stm32 五 + mspm0 二）：框架 → beep（只有初始化）→ sht20（I2C 扫描）"
        "→ servo（认不出初始化）→ led + sht20（两套运行时同堂）→ mspm0 的 ws2812 / aht10。",
        "",
    ]
    missing = [name for name, tool in (("UV4", uv4), ("gmake", make)) if tool is None]
    if missing:
        lines.append(f"**{'、'.join(missing)} 未探测到**：本机缺工具链，那一半矩阵跑不了"
                     "（如实标注，不假装）。")
    LOGS.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="firstep-probe07-"))
    failures = 0
    ran = 0
    try:
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
        for platform, label, devices, uart, oled in VARIANTS:
            tool = uv4 if platform == "stm32" else make
            if tool is None:
                lines.append(f"## [{platform}] {label}：工具链缺失，跳过")
                continue
            response = client.post(
                "/api/hwcheck/generate",
                json={"platform": platform, "debug_uart": uart, "oled": oled,
                      "devices": list(devices), "parent_dir": str(root)},
            )
            if response.status_code != 200:
                lines.append(f"## [{platform}] {label}：生成失败 "
                             f"{response.status_code} "
                             f"{str(response.json().get('detail', ''))[:200]}")
                failures += 1
                continue
            payload = response.json()
            project = Path(payload["output_dir"])
            main_c = (project / "main.c").read_text(encoding="utf-8", errors="replace")
            # 通用小节与载荷对不对得上：通用件应出小节、不在命令表里
            generic = [item["slug"] for item in payload.get("unspecialized") or []]
            commands = [item["slug"] for item in
                        (payload.get("console") or {}).get("commands") or []]
            in_code = [f"static void hwcheck_generic_{slug}(void)" in main_c
                       for slug in generic]
            scan_in_code = "hwcheck_i2c_scan(" in main_c
            pin_config_in_code = '#include "pin_config.h"' in main_c
            if not all(in_code):
                lines.append(f"## [{platform}] {label}：载荷里有通用件 "
                             f"{generic} 但产物里没出小节")
                failures += 1
            if scan_in_code and not pin_config_in_code:
                lines.append(f"## [{platform}] {label}：渲染了总线扫描却没有 "
                             "pin_config.h（引脚宏会未声明）")
                failures += 1
            if set(generic) & set(commands):
                lines.append(f"## [{platform}] {label}：通用件混进了命令表 "
                             f"{sorted(set(generic) & set(commands))}")
                failures += 1
            collector = _Collector()
            try:
                run_compile(platform, project, uv4=uv4 if platform == "stm32" else None,
                            make=make if platform == "mspm0" else None, emit=collector)
            except Exception as exc:  # noqa: BLE001 —— 证据脚本要结论不要栈
                lines.append(f"## [{platform}] {label}：编译执行体抛出 "
                             f"{type(exc).__name__}: {exc}")
                failures += 1
                continue
            ran += 1
            done = next(
                (payload for event, payload in collector.events if event == "done"),
                {},
            )
            parsed = done.get("parsed_errors") or []
            errors = [row for row in parsed if "error:" in str(row.get("message", ""))]
            warnings = [row for row in parsed
                        if "warning:" in str(row.get("message", ""))]
            passed = bool(done.get("passed"))
            summary = done.get("summary") or {}
            lines.append(
                f"## [{platform}] {label}（{project.name}）→ passed={passed} "
                f"exit={done.get('exit_code')} error={len(errors)} "
                f"warning={len(warnings)} 通用小节={generic or '无'} "
                f"扫描={'有' if scan_in_code else '无'} "
                f"pin_config={'有' if pin_config_in_code else '无'} "
                f"命令表={commands or '空'}"
            )
            lines.append(f"  命令：{' '.join(done.get('command') or [])}")
            for row in (errors + warnings)[:12]:
                lines.append(
                    f"  - {row.get('path', '')}:{row.get('line', '')} "
                    f"{str(row.get('message', ''))[:160]}"
                )
            log_text = "\n".join(
                str(payload) for event, payload in collector.events
                if event in ("progress", "done", "error")
            )
            (LOGS / f"{project.name}.log").write_text(log_text, encoding="utf-8")
            if not passed or errors or warnings or summary.get("errors") \
                    or summary.get("warnings"):
                failures += 1
            lines.append("")
        lines.append("## 结论")
        lines.append(
            f"{ran} 种形态真编译，判红 {failures} 种。"
            + ("全部 0 error / 0 warning。" if not failures else "**有形态不过。**")
        )
        lines.append(f"原始日志：{LOGS}")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1 if failures else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
