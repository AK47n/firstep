# -*- coding: utf-8 -*-
"""工单 module-hwcheck/06 的编译矩阵探针（stm32 UV4 + mspm0 gmake 真编译）。

用法：python .scratch/module-hwcheck/probe-06-compile-matrix.py

**为什么要单独一支**：本单往生成的 main.c 里加了**命令台运行时**（`debug_cmd_peek`
/ `debug_cmd_consume` + 一个 `switch` 分派 + 帮助函数），并且动了库内
`debug_uart` 两个平台的 .c/.h。三类新风险只有真编译能发现：

* `switch` 里直接调 `hwcheck_check_<slug>()` —— 函数定义排在命令台之前吗？
  反了就是隐式声明（ARMCC `#223-D` / tiarmclang 警告），验收线 0 warning；
* 库侧新增的 `debug_cmd_peek` / `debug_cmd_consume` 在**两个平台**都能编过吗
  （mspm0 的 `cmd_buf` 是另一份 static）；
* 命令台**有串口就渲染**（工单 06 的评审整改：早先写成"有串口 + 有配方命令"，
  于是"有串口但没配方命令"那格页面说"敲 ? 看帮助"而产物里根本没有命令台——
  假话）——所以框架形态（不选器件）也会带上命令台运行时，要真编一遍看它是不是
  0 error / 0 warning（帮助函数只有 `?` 一个 case 也算"有人调"）。

形态（骨架照工单 05 的那支量具，票面 06 的备忘写着"以后任何生成 C 代码的功能
都能复用"）：**stm32 四形态 + mspm0 两形态**（mspm0 的"器件 + OLED"不能开串口
——默认 OLED_SPI_RES(PA22) 与 DEBUG_UART RX 同脚，生成内核如实 400，是既有事实）。

判据：passed=True 且 error=warning=0。输出：probe-06-compile-matrix.txt +
probe-06-buildlogs/ 下的原始日志。
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
OUT = HERE / "probe-06-compile-matrix.txt"
LOGS = HERE / "probe-06-buildlogs"

# (平台, 标签, 器件, 串口, OLED)
#
# ⚠ mspm0 的"器件 + OLED"形态**不能开串口**：mspm0 默认 OLED_SPI_RES(PA22)
# 与 DEBUG_UART RX 同脚，生成内核如实 400（既有事实，工单 02 的用例钉住了它）。
# 所以 mspm0 只编"框架"与"led + 串口（有命令台）"两形态——后者正是本单的新面。
VARIANTS: tuple[tuple[str, str, tuple[str, ...], bool, bool], ...] = (
    ("stm32", "框架（不选器件：命令台只剩帮助 case）", (), True, False),
    ("stm32", "led + 串口（命令台：l 复测）", ("led",), True, False),
    ("stm32", "led + oled + 双通道（命令台：l / d 复测）", ("led", "oled"), True, True),
    ("stm32", "ml_mpu6050 + 串口（命令台命令调用器件小节）", ("ml_mpu6050",), True, False),
    ("mspm0", "框架（不选器件：命令台只剩帮助 case）", (), True, False),
    ("mspm0", "led + 串口（命令台：库内 peek/consume 的 mspm0 版）", ("led",), True, False),
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
        "# 工单 module-hwcheck/06 编译矩阵（stm32 UV4 + mspm0 gmake 真编译）", "",
        f"UV4：{uv4}",
        f"gmake：{make}",
        f"CCS 三件套：{ccs}",
        "",
        "形态（stm32 四 + mspm0 二）：框架（命令台只剩帮助）→ led（命令台 l）→ "
        "led + oled（l / d）→ ml_mpu6050（命令台调器件小节）。",
        "",
    ]
    missing = [name for name, tool in (("UV4", uv4), ("gmake", make)) if tool is None]
    if missing:
        lines.append(f"**{'、'.join(missing)} 未探测到**：本机缺工具链，那一半矩阵跑不了"
                     "（如实标注，不假装）。")
    LOGS.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="firstep-probe06-"))
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
            # 命令台该不该在：与渲染条件同源（**有串口就有**，不看有没有配方命令）
            commands = (payload.get("console") or {}).get("commands") or []
            has_console = bool(uart)
            main_c = (project / "main.c").read_text(encoding="utf-8", errors="replace")
            console_in_code = "hwcheck_console_poll" in main_c
            if console_in_code != has_console:
                lines.append(f"## [{platform}] {label}：命令台与载荷不一致"
                             f"（载荷 {len(commands)} 条命令 / 代码里"
                             f"{'有' if console_in_code else '没有'}命令台）")
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
                f"warning={len(warnings)} 命令台={'有' if console_in_code else '无'}"
                f"（{len(commands)} 条配方命令）"
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
