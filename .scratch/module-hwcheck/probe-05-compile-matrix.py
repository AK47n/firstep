# -*- coding: utf-8 -*-
"""工单 module-hwcheck/05 的编译矩阵探针（stm32 UV4 + mspm0 gmake 真编译）。

用法：python .scratch/module-hwcheck/probe-05-compile-matrix.py

**为什么要单独一支探针**：本单新增的配方引进了两种"以前从没进过检测工程"的东西：

* stm32 侧调**母版的软 I2C**（`I2C_Init()`，前置调用）+ 读驱动的 **extern 全局量**
  （`ax…gz`）——都在 ml_mpu6050 之外，属"跨模块"；
* mspm0 侧整件走**官方 DMP 库**（inv_mpu.c / inv_mpu_dmp_motion_driver.c /
  mpu_port.c 共 8 个文件），还依赖 SysConfig 的 `I2C_0` 实例——工单 04 的编译矩阵
  从没碰过它（那次只编 led / oled）。

04 的记账里写着"mspm0 侧的真机编译判据留到 05"——本探针就是把那一格补上，并且
**两个平台都编**：形态 = 框架 → ml_mpu6050 专精 → ml_mpu6050 + oled。

判据：passed=True 且 error=warning=0（warning 也记账；04 的口径是 0/0）。
输出：probe-05-compile-matrix.txt + probe-05-buildlogs/ 下的原始日志。
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
OUT = HERE / "probe-05-compile-matrix.txt"
LOGS = HERE / "probe-05-buildlogs"

# (平台, 标签, 器件, 串口, OLED)
#
# ⚠ mspm0 的"ml_mpu6050 + oled"形态**不能开串口**：mspm0 默认 OLED_SPI_RES(PA22)
# 与 DEBUG_UART RX 同脚，生成内核如实 400（既有事实，工单 02 的用例
# `test_generate_endpoint_mspm0_both_channels_conflict_is_reported_400` 钉住了它）。
# 所以那个形态按"只开 OLED"编——用能生成出来的形态验"器件小节 + 另一个输出通道"
# 这件事，而不是把已知的引擎拒绝记成编译失败。
VARIANTS: tuple[tuple[str, str, tuple[str, ...], bool, bool], ...] = (
    ("stm32", "框架（不选器件）", (), True, False),
    ("stm32", "ml_mpu6050 专精", ("ml_mpu6050",), True, False),
    ("stm32", "ml_mpu6050 + oled", ("ml_mpu6050",), True, True),
    ("mspm0", "框架（不选器件）", (), True, False),
    ("mspm0", "ml_mpu6050 专精", ("ml_mpu6050",), True, False),
    ("mspm0", "ml_mpu6050 + oled（只开屏：双通道撞 PA22 是既有事实）",
     ("ml_mpu6050",), False, True),
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
        "# 工单 module-hwcheck/05 编译矩阵（stm32 UV4 + mspm0 gmake 真编译）", "",
        f"UV4：{uv4}",
        f"gmake：{make}",
        f"CCS 三件套：{ccs}",
        "",
        "形态：框架 → ml_mpu6050 专精 → ml_mpu6050 + oled（两个平台各三形态）。",
        "",
    ]
    missing = [name for name, tool in (("UV4", uv4), ("gmake", make)) if tool is None]
    if missing:
        lines.append(f"**{'、'.join(missing)} 未探测到**：本机缺工具链，那一半矩阵跑不了"
                     "（如实标注，不假装）。")
    LOGS.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="firstep-probe05-"))
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
            project = Path(response.json()["output_dir"])
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
            # done 载荷的键是 `passed` / `summary{errors,warnings}`（无 `ok`）：
            # 04 的探针在这一点上踩过坑（读错字段比编译不过更隐蔽），照抄教训。
            parsed = done.get("parsed_errors") or []
            errors = [row for row in parsed if "error:" in str(row.get("message", ""))]
            warnings = [row for row in parsed
                        if "warning:" in str(row.get("message", ""))]
            passed = bool(done.get("passed"))
            summary = done.get("summary") or {}
            lines.append(
                f"## [{platform}] {label}（{project.name}）→ passed={passed} "
                f"exit={done.get('exit_code')} error={len(errors)} "
                f"warning={len(warnings)}"
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
