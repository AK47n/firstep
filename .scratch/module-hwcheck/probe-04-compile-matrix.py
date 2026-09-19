# -*- coding: utf-8 -*-
"""工单 module-hwcheck/04 的编译矩阵探针（stm32 / UV4 真编译）。

用法：python .scratch/module-hwcheck/probe-04-compile-matrix.py

**为什么要单独一支探针**：spec 的真机口径写着「stm32 UV4 / mspm0 gmake 编译绿」，
而 tickets 03 的证据链里编译绿的是**未选器件**的框架形态——本单新增了逐件小节
（配方渲染的调用 + 判定记账 + 中文字符串字面量），那部分有没有编过，没有任何
既有证据能回答。本探针把四种形态各生成一次、各真编译一次，逐形态记 error/warning
数并落原始 buildlog。

形态：`[]`（框架）→ `["led"]` → `["oled"]` → `["led","oled"]`。
输出：probe-04-compile-matrix.txt + probe-04-buildlogs/ 下的原始日志。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.compile_runner import find_uv4, run_compile  # noqa: E402
from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.sse import SseEmitter  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe-04-compile-matrix.txt"
LOGS = HERE / "probe-04-buildlogs"

VARIANTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("框架（不选器件）", ()),
    ("led 专精", ("led",)),
    ("oled 专精", ("oled",)),
    ("led + oled 专精", ("led", "oled")),
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
    lines: list[str] = [
        "# 工单 module-hwcheck/04 编译矩阵（stm32 / UV4 真编译）", "",
        f"UV4：{uv4}", "",
    ]
    if uv4 is None:
        lines.append("**UV4 未探测到**：本机没有 Keil，编译矩阵跑不了（如实标注，不假装）。")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1
    LOGS.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="firstep-probe04-"))
    failures = 0
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
        for label, devices in VARIANTS:
            response = client.post(
                "/api/hwcheck/generate",
                json={"platform": "stm32", "debug_uart": True, "oled": False,
                      "devices": list(devices), "parent_dir": str(root)},
            )
            if response.status_code != 200:
                lines.append(f"## {label}：生成失败 {response.status_code} "
                             f"{response.json().get('detail', '')[:160]}")
                failures += 1
                continue
            project = Path(response.json()["output_dir"])
            collector = _Collector()
            try:
                run_compile("stm32", project, uv4=uv4, make=None, emit=collector)
            except Exception as exc:  # noqa: BLE001 —— 证据脚本要结论不要栈
                lines.append(f"## {label}：编译执行体抛出 {type(exc).__name__}: {exc}")
                failures += 1
                continue
            done = next(
                (payload for event, payload in collector.events if event == "done"),
                {},
            )
            # done 载荷的键是 `passed` / `summary{errors,warnings}`（无 `ok`）：
            # 早期版本按 `ok` 取值，于是四种形态全被判红——判据读错字段比编译
            # 不过更隐蔽（本探针自己踩过，写下来）
            parsed = done.get("parsed_errors") or []
            errors = [row for row in parsed if "error:" in str(row.get("message", ""))]
            warnings = [row for row in parsed
                        if "warning:" in str(row.get("message", ""))]
            passed = bool(done.get("passed"))
            summary = done.get("summary") or {}
            lines.append(
                f"## {label}（{project.name}）→ passed={passed} "
                f"exit={done.get('exit_code')} error={len(errors)} "
                f"warning={len(warnings)}"
            )
            for row in errors[:12]:
                lines.append(
                    f"  - {row.get('path', '')}:{row.get('line', '')} "
                    f"{str(row.get('message', ''))[:140]}"
                )
            log_text = "\n".join(
                str(payload) for event, payload in collector.events
                if event in ("progress", "done", "error")
            )
            (LOGS / f"{project.name}.log").write_text(log_text, encoding="utf-8")
            if not passed or errors or summary.get("errors"):
                failures += 1
            lines.append("")
        lines.append("## 结论")
        lines.append(
            f"{len(VARIANTS)} 种形态，判红 {failures} 种。"
            + ("全部编译绿。" if not failures else "**有形态编译不过**。")
        )
        lines.append(f"原始日志：{LOGS}")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1 if failures else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
