# -*- coding: utf-8 -*-
"""工单 module-hwcheck/09 的编译矩阵探针（stm32 UV4 + mspm0 gmake 真编译）。

用法：python .scratch/module-hwcheck/probe-09-compile-matrix.py

**为什么要单独一支**：本单把 pilot 清单补到 10 件 / 17 格，其中 11 格是**第一次
进产物**（debug_uart / key / beep / sr04 / jy61p / xunji / adc）——每一格都要过
"真编译 0 error / 0 warning"这条既定验收线，而这只有真工具链说了算：实参类型
（枚举 vs 整型 → `#188-D`）、头文件是否真被 include（`pin_config.h`）、以及
"渲染出来的名字在真工程里存不存在"都只有编译器能给结论。

**两种结果分开记**（本探针的核心口径）：

* **能生成 → 真编译**：判据 = passed 且 error=warning=0。通道形态按顺序试
  「只开串口 → 只开 OLED → 都不开」，取第一个能生成的——检测页两种通道都
  有各自的用途，矩阵要覆盖的是**配方**，不是通道组合。
* **生成前就被拦下**：**分两类**（工单 hwcheck-pin-conflict-exit/01 起）——
  ① **缺陷式拦下**：400 里没有检测页能执行的出路（学生按默认状态点生成，
     拿到的是一句指向赛题页的话）。这一类记进 `生成前拦下` 一节，**算判红**。
  ② **如实拦下**：400 带页面出路（被判据点名是哪些脚、哪几件、能怎么去掉）。
     这一类记进 `如实拦下（页面已说明原因）` 一节，**不算判红**——板子真的装不下时，
     拦下才是对的；判据是「有没有给学生做得到的话」，不是「能不能生成」。
  同时逐格记录**默认形态**（串口 + OLED 都开，就是检测页打开时的样子）能不能生成
  ——这一列是"检测页默认必 400"那条缺陷的直接证据。

输出：probe-09-compile-matrix.txt + probe-09-buildlogs/ 下的原始日志。
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
from contest_generator.hwcheck_board import HWCHECK_PIN_EXIT_MARKER  # noqa: E402
from contest_generator.sse import SseEmitter  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe-09-compile-matrix.txt"
LOGS = HERE / "probe-09-buildlogs"

# pilot 清单**单源**：直接取地板断言那份 `PILOT`（tests/test_hwcheck_recipe.py）。
# 这份清单曾经在三个地方各手抄一遍（测试 / 校验器 / 本探针），第三份当场漂移
# ——本单评审抓到：矩阵自称"17 格"却漏了 adc×mspm0。抄一遍就是赌它不会漂。
sys.path.insert(0, str(REPO))
from tests.test_hwcheck_recipe import PILOT  # noqa: E402

_CELLS: tuple[tuple[str, str, tuple[str, ...]], ...] = tuple(
    (platform, slug, (slug,)) for slug, platform in PILOT
) + (
    ("stm32", "全选（7 件同堂）",
     ("led", "oled", "debug_uart", "key", "beep", "adc", "ml_mpu6050")),
    ("mspm0", "全选（9 件同堂）",
     ("led", "oled", "debug_uart", "key", "beep", "sr04", "jy61p", "xunji", "ml_mpu6050")),
)

# 通道形态候选（按顺序试，取第一个能生成的）：只开串口 → 只开 OLED → 都不开
_CHANNELS: tuple[tuple[bool, bool], ...] = ((True, False), (False, True), (False, False))

# 检测页默认形态（两通道都开）——单独记一列，是"默认脚冲突"的直接证据
_DEFAULT = (True, True)


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


def _first_line(detail: str) -> str:
    for line in str(detail).splitlines():
        if line.strip():
            return line.strip()
    return ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    uv4 = find_uv4()
    make = find_make()
    ccs = find_ccs_tools()
    lines: list[str] = [
        "# 工单 module-hwcheck/09 编译矩阵"
        f"（pilot {len(PILOT)} 格 + {len(_CELLS) - len(PILOT)} 格全选；"
        "stm32 UV4 / mspm0 gmake）", "",
        f"UV4：{uv4}",
        f"gmake：{make}",
        f"CCS 三件套：{ccs}",
        "",
        "判据：能生成的那一格 → passed=True 且 error=warning=0。被拦下的按**页面有没有"
        "给出学生做得到的出路**分两类（工单 hwcheck-pin-conflict-exit/01）：有出路 = "
        "「如实拦下」（板子真装不下，不算判红）；没有 = 「生成前拦下」（缺陷，算判红）。",
        "⚠ **逐格用的通道形态是「只串口 → 只 OLED → 都不开」里第一个能生成的那个**"
        "（每行末尾记着它）；每行末尾另记检测页默认形态（串口 + OLED 都开）的状态。",
        "",
    ]
    missing = [name for name, tool in (("UV4", uv4), ("gmake", make)) if tool is None]
    if missing:
        lines.append(f"**{'、'.join(missing)} 未探测到**：本机缺工具链，那一半矩阵跑不了"
                     "（如实标注，不假装）。")
    LOGS.mkdir(exist_ok=True)
    # 每次重跑先清日志目录：不然上一轮的 buildlog 混在里头，读的人分不清哪份是这次的
    for stale in LOGS.glob("*.log"):
        stale.unlink()
    root = Path(tempfile.mkdtemp(prefix="firstep-probe09-"))
    compiled = 0
    failures = 0
    blocked: list[str] = []
    honest: list[str] = []
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

        def generate(platform: str, devices: tuple[str, ...], uart: bool, oled: bool):
            return client.post(
                "/api/hwcheck/generate",
                json={"platform": platform, "debug_uart": uart, "oled": oled,
                      "devices": list(devices), "parent_dir": str(root)},
            )

        def preview(platform: str, devices: tuple[str, ...], uart: bool, oled: bool):
            return client.post(
                "/api/hwcheck/preview",
                json={"platform": platform, "debug_uart": uart, "oled": oled,
                      "devices": list(devices)},
            )

        def classify(note: str) -> str:
            """拦下归哪一类：页面有没有给学生做得到的出路（本单的验收线）。"""
            return "honest" if HWCHECK_PIN_EXIT_MARKER in note else "defect"

        for platform, label, devices in _CELLS:
            tool = uv4 if platform == "stm32" else make
            if tool is None:
                lines.append(f"## [{platform}] {label}：工具链缺失，跳过")
                continue
            default_response = generate(platform, devices, *_DEFAULT)
            default_note = ("默认双通道可生成" if default_response.status_code == 200
                            else "默认双通道 400：" + _first_line(
                                default_response.json().get("detail", ""))[:120])
            chosen = None
            last_detail = ""
            for uart, oled in _CHANNELS:
                response = generate(platform, devices, uart, oled)
                if response.status_code == 200:
                    chosen = (uart, oled, response.json())
                    break
                last_detail = str(response.json().get("detail", ""))
            if chosen is None:
                item = f"[{platform}] {label}：三种通道形态都生成不了（{default_note}）"
                if classify(last_detail) == "honest":
                    honest.append(item + f"；页面已说明：{HWCHECK_PIN_EXIT_MARKER}…")
                    lines.append(f"## [{platform}] {label}：**如实拦下（页面已说明）**"
                                 f"（{default_note}）")
                else:
                    blocked.append(item + "；400 里没有页面出路")
                    lines.append(f"## [{platform}] {label}：**生成前拦下**（{default_note}）")
                lines.append("")
                continue
            uart, oled, payload = chosen
            project = Path(payload["output_dir"])
            main_c = (project / "main.c").read_text(encoding="utf-8", errors="replace")
            sections = [item["slug"] for item in payload.get("sections") or []]
            # 「两个通道都不开」也能生成，但那一形态**按设计不渲染逐件小节**
            # （它只验"板子活着"）——拿它当"这一格编译过了"就是报喜不报忧：
            # 这一格到不了板，如实记进"生成前拦下"。
            if not (uart or oled) and sections:
                blocked.append(
                    f"[{platform}] {label}：三种通道形态里只有「都不开」能生成，"
                    "而那一形态不渲染逐件小节（这一格到不了板）"
                )
                lines.append(f"## [{platform}] {label}：**生成前拦下**"
                             "（只有「都不开」能生成 → 不渲染逐件小节）")
                lines.append("")
                continue
            unspecialized = [item["slug"] for item in payload.get("unspecialized") or []]
            commands = [(item["slug"], item["command"])
                        for item in (payload.get("console") or {}).get("commands") or []]
            section_in_code = [slug for slug in sections
                               if f"hwcheck_check_{slug}(" in main_c]
            # 无输出通道时逐件小节按设计不渲染（"这一趟只验板子活着"那条路）
            if (uart or oled) and len(section_in_code) != len(sections):
                lines.append(f"## [{platform}] {label}：载荷小节 {sections} "
                             f"与产物不一致（产物里只有 {section_in_code}）")
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
            compiled += 1
            done = next(
                (payload for event, payload in collector.events if event == "done"), {},
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
                f"warning={len(warnings)} 专精小节={sections or '无'} "
                f"未专精={unspecialized or '无'} "
                f"命令表={' '.join(f'{c}={s}' for s, c in commands) or '空'} "
                f"｜通道=串口{int(uart)}/OLED{int(oled)}（{default_note}）"
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

        lines.append("## 生成前拦下（缺陷：400 里没有检测页能执行的出路）")
        if blocked:
            lines.extend(f"- {item}" for item in blocked)
        else:
            lines.append("- （无）")
        lines.append("")
        lines.append("## 如实拦下（页面已说明原因，不算判红）")
        if honest:
            lines.extend(f"- {item}" for item in honest)
        else:
            lines.append("- （无）")
        lines.append("")
        # 预览 / 生成判据一致（工单 hwcheck-pin-conflict-exit/01 的验收线之一）：
        # 同一形态两边状态码必须一样——"预览通过、点生成才失败"是这条单要灭的分家。
        mismatches: list[str] = []
        for platform, label, devices in _CELLS:
            if (uv4 if platform == "stm32" else make) is None:
                continue
            p = preview(platform, devices, *_DEFAULT)
            g = generate(platform, devices, *_DEFAULT)
            if p.status_code != g.status_code:
                mismatches.append(
                    f"[{platform}] {label}：预览 {p.status_code} / 生成 {g.status_code}"
                )
        lines.append("## 预览 / 生成判据一致（默认形态逐格）")
        if mismatches:
            lines.extend(f"- {item}" for item in mismatches)
            failures += len(mismatches)
        else:
            lines.append("- 全部一致（逐格两边同码）")
        lines.append("")
        lines.append("## 结论")
        lines.append(
            f"{compiled} 种形态真编译，判红 {failures} 种，生成前拦下 {len(blocked)} 种，"
            f"如实拦下 {len(honest)} 种"
            f"（pilot {len(PILOT)} 格 + {len(_CELLS) - len(PILOT)} 格全选；每格用的通道形态见上文每行末尾）。"
            + ("真编译的部分全部 0 error / 0 warning。" if not failures else "**有形态不过。**")
        )
        lines.append(f"原始日志：{LOGS}")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 1 if failures else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
