# -*- coding: utf-8 -*-
"""工单 module-hwcheck/07 的**判据强度探针**：逐条注入缺陷，看对应用例变不变红。

用法：python .scratch/module-hwcheck/negative-verify-07.py

本仓库的既有纪律（04/05/06 同款）：每条新守卫都要有一次"停用 / 改坏之后用例
必须变红"的实测——不然那条守卫可能只是**摆设**（改坏了还全绿）。本探针把每条
注入打成"改文件 → 跑指定用例 → 期望红 → 复原 → 逐字节核对复原干净"。

覆盖的守卫（注入编号 → 被它钉住的判据）：

| # | 注入 | 该红的用例 |
|---|---|---|
| A | 初始化判据不再要求"无参声明" | 要参数的初始化不许被调 |
| B | 认不出时返回 `<slug>_init`（编一个出来） | 没有头文件时不认 |
| C | 多个候选里取第一个（猜一个） | 两个候选时不许猜 |
| D | 扫描不再要求引脚宏 | mspm0 侧的 I2C 角色不许扫 |
| E | 扫描不再要求两个角色都在 | 只有 SCL 不许扫 |
| F | 「未专精」措辞改成第二句 | 措辞单源 |
| G | 通用小节里塞一个读调用 | 通用段落只有初始化一个模块调用 |
| H | 通用小节带上 `[专精]` 标记 | 通用件不许带专精标记 |
| I | 通用件混进命令台分派 | 命令台从不分派通用件 |
| J | 没有输出通道也渲染通用小节 | 通用小节同样要有输出通道 |
| K | 没有扫描也渲染 ping 助手 | 按需渲染（0 warning 线） |
| L | 产物不 include pin_config.h | 扫描必须把引脚宏带进来 |
| M | 规划不再过滤专精件 | 一件恰好进一个桶 |
| N | 规划不去重（同一件两条小节） | 同一件选两次只出一条 |
| O | 载荷的未专精点名不带标注 | 端点载荷带「未专精」原话 |
| P | 通用件不带 probe_none 计数 | 只有通用件时的共用运行时齐备 |
| Q | 前端丢掉 label / plan | 检测页说清这一趟做什么 |
| R | 标注不按真做了什么分（一律印「只验总线和初始化」） | 什么都没做的件不许假装验过初始化 |
| S | 扫不了时不说理由（静默收窄） | 声明了 I2C 角色却没扫要给说法 |
| T | 「无应答」文案写回超长 | 行缓冲守卫（128 字节） |
| U | 帮助行写回一条龙 | 行缓冲守卫（管住 06 的既有超长行） |

输出：negative-verify-07.txt（每条注入的实测结果 + 复原核对）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "negative-verify-07.txt"

SRC = REPO / "src" / "contest_generator"
GENERIC = SRC / "hwcheck_generic.py"
HWCHECK = SRC / "hwcheck.py"
WEBAPP = SRC / "webapp.py"
FX = SRC / "static" / "js" / "fx" / "hwcheck.js"
CONSOLE = SRC / "hwcheck_console.py"

TEST_GENERIC = "tests/test_hwcheck_generic.py"
TEST_HWCHECK = "tests/test_hwcheck.py"

# (编号, 说明, 文件, 原文, 替换, 用例文件, 用例名, 跑法)
#   跑法 = "py"（pytest -k）或 "js"（node --test）
INJECTIONS: tuple[tuple[str, str, Path, str, str, str, str, str], ...] = (
    (
        "A", "初始化判据不再要求无参声明（接受要参数的初始化）", GENERIC,
        "    forms = declarations.get(name)\n    return bool(forms) and forms <= _NO_PARAM_FORMS",
        "    forms = declarations.get(name)\n    return bool(forms)",
        TEST_GENERIC, "test_plan_init_refuses_an_init_that_needs_arguments", "py",
    ),
    (
        "B", "认不出时编一个 <slug>_init 出来", GENERIC,
        "    exact = f\"{slug}_init\"\n    if _callable_without_arguments(exact, declarations):\n        return InitPlan(name=exact)",
        "    exact = f\"{slug}_init\"\n    return InitPlan(name=exact)",
        TEST_GENERIC, "test_plan_init_is_empty_without_any_header", "py",
    ),
    (
        "C", "多个候选里猜第一个", GENERIC,
        "    if len(candidates) == 1:\n        return InitPlan(name=candidates[0])",
        "    if candidates:\n        return InitPlan(name=candidates[0])",
        TEST_GENERIC, "test_plan_init_refuses_to_guess_between_two_candidates", "py",
    ),
    (
        "D", "扫描不再要求引脚宏", GENERIC,
        "    if len(scl.macros) != 2 or len(sda.macros) != 2:\n        return None",
        "    if False:\n        return None",
        TEST_GENERIC,
        "test_real_library_mspm0_i2c_roles_carry_no_pin_macros_so_no_scan", "py",
    ),
    (
        "E", "扫描不再要求两个角色都在", GENERIC,
        "    if scl is None or sda is None:\n        return None",
        "    if scl is None:\n        return None\n    if sda is None:\n        sda = scl",
        TEST_GENERIC, "test_scan_for_pins_needs_both_roles", "py",
    ),
    (
        "F", "「未专精」措辞改成第二句", GENERIC,
        'GENERIC_LABEL = "未专精：只验总线和初始化"',
        'GENERIC_LABEL = "未专精：只验总线"',
        TEST_GENERIC, "test_real_library_generic_label_is_the_single_source_wording", "py",
    ),
    (
        "G", "通用小节里塞一个读调用（猜读函数）", GENERIC,
        "    out.append(\"    hwcheck_newline();\")\n    if section.scan is not None:",
        "    out.append(\"    hwcheck_newline();\")\n    out.append(f\"    {section.slug}_read();\")\n    if section.scan is not None:",
        TEST_GENERIC, "test_render_generic_section_never_calls_anything_but_the_init", "py",
    ),
    (
        "H", "通用小节带上 [专精] 标记", GENERIC,
        '        f"    /* ---- {label} ---- */",',
        '        f"    /* ---- [专精] {label} ---- */",',
        TEST_GENERIC, "test_render_generic_section_carries_the_label_and_not_the_specialized_tag", "py",
    ),
    (
        "I", "命令台也分派通用件", HWCHECK,
        '    if console_rendered:\n        lines.extend(render_console_runtime(console))',
        '    if console_rendered:\n        lines.extend(render_console_runtime(console))\n        for section in generic:\n            lines.append(f"        case 0: hwcheck_generic_{section.slug}(); break;")',
        TEST_HWCHECK, "test_the_console_never_dispatches_a_generic_section", "py",
    ),
    (
        "J", "没有输出通道也渲染通用小节", HWCHECK,
        "    if generic and config.has_output_channel:\n        lines.append(f\"/* ---- 通用降级小节",
        "    if generic:\n        lines.append(f\"/* ---- 通用降级小节",
        TEST_HWCHECK, "test_generic_sections_require_an_output_channel_too", "py",
    ),
    (
        "K", "没有扫描也渲染 ping 助手", GENERIC,
        "    if not any(section.scan is not None for section in sections):\n        return []",
        "    if False:\n        return []",
        TEST_HWCHECK, "test_a_scan_less_generic_run_declares_no_ping_helper", "py",
    ),
    (
        "L", "产物不 include pin_config.h", HWCHECK,
        '    if scan_rendered and headers["pin_config"]:\n        lines.append(\n            f\'#include "{headers["pin_config"]}"',
        '    if False:\n        lines.append(\n            f\'#include "{headers["pin_config"]}"',
        TEST_HWCHECK, "test_a_bus_scan_brings_in_pin_config_and_resolves_it", "py",
    ),
    (
        "M", "规划不再过滤专精件", GENERIC,
        "        if slug in specialized_set or slug in planned:\n            continue",
        "        if slug in planned:\n            continue",
        TEST_GENERIC, "test_every_device_ends_up_in_exactly_one_bucket", "py",
    ),
    (
        "N", "规划不去重（同一件出两条小节）", GENERIC,
        "        if slug in specialized_set or slug in planned:\n            continue",
        "        if slug in specialized_set:\n            continue\n        if slug in planned:\n            planned[slug + \"-dup\"] = planned[slug]\n            continue",
        TEST_GENERIC, "test_resolve_generic_sections_is_idempotent_for_a_repeated_device", "py",
    ),
    (
        "O", "载荷的未专精点名不带标注", WEBAPP,
        '                    "label": section.label,',
        '                    "label": "",',
        TEST_HWCHECK, "test_preview_reports_devices_without_a_recipe_as_unspecialized", "py",
    ),
    (
        "P", "通用件不带 probe_none 计数（共用运行时缺一块）", HWCHECK,
        "                needs_probe_none=_needs_probe_none(sections) or bool(generic),",
        "                needs_probe_none=_needs_probe_none(sections),",
        TEST_HWCHECK, "test_generic_only_artifact_calls_no_undefined_helper", "py",
    ),
    (
        "Q", "前端丢掉 label / plan（只回显旧那句）", FX,
        '    const label = String(one.label || "");\n    const plan = String(one.plan || "");',
        '    const label = "";\n    const plan = "";',
        "tests/js/hwcheck.test.mjs",
        "hwcheckUnspecializedHTML：没配方的件逐条点名 + 说清这一趟做什么（工单 07）",
        "js",
    ),
    (
        "R", "标注不按「真做了什么」分（一律印只验总线和初始化）", GENERIC,
        "        if self.init.name:\n            return GENERIC_LABEL\n        if self.scan is not None:\n            return GENERIC_LABEL_SCAN_ONLY\n        return GENERIC_LABEL_IDLE",
        "        return GENERIC_LABEL",
        TEST_GENERIC, "test_plan_generic_section_without_a_callable_init_still_plans_and_says_why", "py",
    ),
    (
        "S", "声明了 I2C 角色却扫不了时不说理由", GENERIC,
        "        scan_note=(\n            _scan_note(entry.pins) if scan is None and entry is not None else \"\"\n        ),",
        "        scan_note=\"\",",
        TEST_GENERIC, "test_plan_generic_section_says_why_it_did_not_scan_an_i2c_device", "py",
    ),
    (
        "T", "「无应答」那行写回超长文案（撞 128 字节行缓冲）", GENERIC,
        '            "    无应答：先查供电 / 上拉 / 线序（有没有接反）"',
        '            "    无应答：这一段地址一个都没回——先查供电、上拉（SDA/SCL 各要 4.7k）、线序（有没有接反）"',
        TEST_HWCHECK, "test_every_reported_line_fits_the_line_buffer", "py",
    ),
    (
        "U", "帮助行写回一条龙（06 的既有超长行）", CONSOLE,
        "            if len(row) == _LEGACY_PER_HELP_LINE:\n                legacy_rows.append(\"    \" + \" / \".join(row))\n                row = []",
        "            if False:\n                legacy_rows.append(\"    \" + \" / \".join(row))\n                row = []",
        TEST_HWCHECK, "test_every_reported_line_fits_the_line_buffer", "py",
    ),
)


def _run_py(test_file: str, test_name: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-q", "-k", test_name,
         "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def _run_js(test_file: str, test_name: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["node", "--test", test_file, "--test-name-pattern", test_name],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    lines: list[str] = [
        "# 工单 module-hwcheck/07 判据强度探针（逐条注入 → 对应用例必须变红）", "",
    ]
    failures = 0
    lines.append(
        "每条注入都先跑一遍**基线**（未注入时那条例用必须绿），再注入看它变红，"
        "最后逐字节复原——所以「工作区有未提交改动」不影响本探针的结论。"
    )
    lines.append("")
    baseline: dict[tuple[str, str], tuple[int, str]] = {}
    for number, note, path, old, new, test_file, test_name, runner in INJECTIONS:
        original = path.read_text(encoding="utf-8")
        if old not in original:
            lines.append(f"## {number} {note}：**注入点找不到**（探针自己过期了）")
            failures += 1
            continue
        key = (test_file, test_name, runner)
        if key not in baseline:
            run = _run_py if runner == "py" else _run_js
            baseline[key] = run(test_file, test_name)
        base_code, base_output = baseline[key]
        if base_code != 0:
            lines.append(f"## {number} {note}：**基线就是红的**（注入前那条例用没过，"
                         f"退出码 {base_code}）——本条的结论不算数")
            failures += 1
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            run = _run_py if runner == "py" else _run_js
            code, output = run(test_file, test_name)
        finally:
            path.write_text(original, encoding="utf-8")
        restored = path.read_text(encoding="utf-8") == original
        red = code != 0
        if not red:
            failures += 1
        lines.append(
            f"## {number} {note}：{'变红 ✓' if red else '**仍绿 ✗**'}"
            f"（用例 {test_name}，退出码 {code}，复原{'干净 ✓' if restored else '**不干净 ✗**'}）"
        )
        if not red:
            tail = [row for row in output.splitlines() if row.strip()][-4:]
            lines.append("```\n" + "\n".join(tail) + "\n```")
        if not restored:
            failures += 1
        lines.append("")
    total = len(INJECTIONS)
    lines.append("## 结论")
    lines.append(f"{total} 条注入，判红失败 {failures} 条。"
                 + ("全部注入后对应用例变红、文件逐字节复原。"
                    if not failures else "**有注入没被抓住。**"))
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
