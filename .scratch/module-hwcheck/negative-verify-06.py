# -*- coding: utf-8 -*-
"""工单 module-hwcheck/06 判据强度探针：**停用每一条新守卫 → 对应用例必须变红**。

本仓库既有纪律（工单 01–05 同款）：新守卫不能只证明"现在是绿的"——还要证明
"坏了会红"。本脚本逐条注入故障、跑对应用例、记下红证，最后逐字节复原。

本单的守卫集中在四类坏法：

① **字符冲突不再判**（两件抢一个字符 / 配方抢占既有 r/y/g/o/b 或帮助 ?）
   ——那正是票面点名的"构建期报错，不是运行时静默覆盖"；
② **既有命令被抢**（分派树里不再 `return` 而是 `break` + 消费 / 库侧 peek 顺手
   清空 / 镜像表漏登记一条）——学生敲 r 不再点灯，且是最难查的一类静默失效；
③ **命令台该在的时候不在**（无串口也渲染 / 有串口却不 peek / 主循环顺序倒过来
   / case 不调那件的小节）——"复测不用重烧"整件事不成立；
④ **页面与产物不同源**（载荷不再带命令表 / 无串口却印"能交互复测" /
   前端不做转义 / 没有串口时照摆命令表）。

用法：python .scratch/module-hwcheck/negative-verify-06.py
输出：negative-verify-06.txt（每条：注入点 / 用例 / 退出码 / 红证摘要）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "negative-verify-06.txt"

# (编号, 说明, 相对路径, 原文片段, 注入片段, 跑法标记 + 参数)
# 跑法标记：`py:<-k 选择器>` = python -m pytest；`js:<用例名>` = node --test
MUTATIONS: list[tuple[str, str, str, str, str, list[str]]] = [
    (
        "A",
        "**配方抢占库内既有命令字符不再拦**（保留字判据停用）：学生敲 r 会去复测"
        "某件器件而不再点灯（已上过板的既有行为被抢）——票面点名的构建期判据",
        "src/contest_generator/hwcheck_console.py",
        "        if key in RESERVED_COMMANDS:",
        "        if False:",
        ["py:test_recipe_may_not_take_over_a_library_command_character"],
    ),
    (
        "B",
        "**两件抢同一个字符不再拦**（重复判据停用）：命令循环按字符分派，"
        "后一件永远测不到（运行时静默覆盖）",
        "src/contest_generator/hwcheck_console.py",
        "        if key in seen:",
        "        if False:",
        ["py:two_devices_may_not_share_a_command_character or "
         "build_time_when_two_devices_share_a_command"],
    ),
    (
        "C",
        "**既有命令那一支改成 `break`（继续走到消费）**：库内 poll 再也收不到 "
        "r/y/g/o/b，五条既有命令全体静默失效",
        "src/contest_generator/hwcheck_console.py",
        '    out.append("        return;")',
        '    out.append("        break;")',
        ["py:hands_the_library_commands_back_untouched"],
    ),
    (
        "D",
        "**镜像表漏登记一条既有命令**（LEGACY_COMMANDS 去掉 b）：库内 poll 认它、"
        "我们却不认，配方可以抢走 b<N> 的蜂鸣",
        "src/contest_generator/hwcheck_console.py",
        '    ("b", "蜂鸣器响 N 毫秒（如 b50）"),\n',
        "",
        ["py:legacy_command_mirror_matches_the_library_dispatch or "
         "legacy_command_set_is_the_library_protocol"],
    ),
    (
        "E",
        "**库侧 peek 顺手清空缓冲**（只读契约破坏）：既有 r/y/g/o/b 永远收不到命令"
        "（库内 poll 拿到空串）",
        "library/modules/debug_uart/code/debug_uart.c",
        "    return cmd_buf;     // 没有完整命令时是空串（首字符 '\\0'）",
        "    cmd_buf[0] = '\\0';\n    return cmd_buf;",
        ["py:peek_is_read_only_and_consume_is_the_only_consumer"],
    ),
    (
        "F",
        "**主循环顺序倒过来**（先库内 poll 再我们的）：库内 poll 先把缓冲清空，"
        "配方命令永远认不出来——本探针的兄弟 `probe-06-console-behaviour.py` "
        "有这条的真跑反证",
        # ⚠ 注入必须**语法合法**（首轮写成"删掉那一行"，结果 `if console_rendered:`
        # 成空体 → SyntaxError → pytest 收集期就红（exit=2），一条用例都没跑，
        # 却计进了"注入后变红"——那不是守卫有牙，是探针自己在崩。评审抓到的。）
        "src/contest_generator/hwcheck.py",
        '            lines.append("        hwcheck_console_poll();  '
        '/* 配方命令：复测不用重烧 */")\n'
        '        lines.append("        debug_cmd_poll();  '
        '/* 串口命令通道：复测不用重烧 */")',
        # ⚠ 注入必须**语法合法**：首版写成"删掉那一行"，结果是 `if console_rendered:`
        # 空体 → IndentationError → pytest 收集期就红（exit=2），一条用例都没跑，
        # 却计进了"注入后变红"——那不是守卫有牙，是探针自己在崩（评审抓到的）。
        # 现在是把两句**换个顺序**（最内层仍留一句合法的 body）。
        '            lines.append("        debug_cmd_poll();  '
        '/* 反证：先库内 */")\n'
        '        if console_rendered:\n'
        '            lines.append("        hwcheck_console_poll();  '
        '/* 反证：顺序倒过来 */")',
        ["py:polls_our_console_before_the_library_poll"],
    ),
    (
        "G",
        "**无串口也渲染命令台**（渲染条件丢掉 debug_uart）：产物里出现一个跑不到的"
        "命令循环，页面还说能复测——不静默降级那条验收线失效",
        "src/contest_generator/hwcheck.py",
        "    console_rendered = bool(config.debug_uart)",
        "    console_rendered = True",
        ["py:without_serial_says_interactive_retest_is_impossible"],
    ),
    (
        "H",
        "**复测的第三段没了**（case 不再调那一件的小节）：回显只剩「这是哪件 / "
        "测的是什么」，结论与数值永远不出现",
        "src/contest_generator/hwcheck_console.py",
        '        out.append(f"        hwcheck_check_{entry.slug}();")',
        '        out.append(f"        /* hwcheck_check_{entry.slug}(); */")',
        ["py:retest_echo_has_the_three_fixed_segments"],
    ),
    (
        "I",
        "**未知命令静默丢弃**（default 分支不再印帮助）：学生敲错一个字符就再无"
        "任何反馈，也不知道有哪些命令",
        "src/contest_generator/hwcheck_console.py",
        '        "        hwcheck_console_help();",\n',
        "",
        ["py:reports_unknown_commands_with_a_help_line"],
    ),
    (
        "J",
        "**无串口时也印「能交互复测」**（hint 的通道判据停用）：页面说了假话"
        "——「没有串口 = 不能交互式复测」这条验收线失效",
        "src/contest_generator/hwcheck_console.py",
        "    if not debug_uart:\n        return CONSOLE_HINT_NONE",
        "    if False:\n        return CONSOLE_HINT_NONE",
        ["py:says_out_loud_when_there_is_no_serial or "
         "says_out_loud_when_there_is_no_serial_endpoint or "
         "marks_availability_false_without_serial"],
    ),
    (
        "K",
        "**载荷不再带命令表**（commands 恒为空）：页面说不出敲什么字符，"
        "而板上认它——页面与产物两个来源",
        "src/contest_generator/hwcheck_console.py",
        '            for entry in table.entries\n        ],',
        '            for entry in []\n        ],',
        ["py:payload_carries_the_table_and_the_legacy_commands"],
    ),
    (
        "L",
        "**前端命令表不做转义**（配方说明里出现 < > 就破页面）：库内数据是"
        "不可信文本",
        "src/contest_generator/static/js/fx/hwcheck.js",
        '+ `<td>${esc(one.description || "")}</td></tr>`;',
        '+ `<td>${one.description || ""}</td></tr>`;',
        ["js:hwcheckConsoleHTML：文案过转义"],
    ),
    (
        "M",
        "**没有串口时照摆命令表**（前端 available 判据停用）：摆一张这一趟根本"
        "敲不了的表，像「敲了就行」",
        "src/contest_generator/static/js/fx/hwcheck.js",
        "  if (data.available === false) {",
        "  if (false) {",
        ["js:hwcheckConsoleHTML：没有串口时"],
    ),
    (
        "N",
        "**命令字符不再规范化成小写**（声明 `L` 原样进表）：渲染器为它出"
        "`case 'L': case 'L':` 两个**重复标签**——生成的 main.c 编不过，"
        "而表里按小写判重又允许同一个字符被声明两次",
        "src/contest_generator/hwcheck_console.py",
        "        command = command.lower()\n",
        "",
        ["py:uppercase_declaration_is_normalized_to_the_canonical_form"],
    ),
]


def _anchor_count(rel: str, old: str, text: str) -> int:
    return text.count(old)


def _run(target: list[str]) -> tuple[int, str]:
    """`target[0]` = `py:<选择器>` / `js:<用例名>`（`or` 连起来的选择器表达式）。"""
    kind, _, expression = target[0].partition(":")
    if kind == "js":
        proc = subprocess.run(
            ["node", "--test", "--test-name-pattern", expression,
             "tests/js/hwcheck.test.mjs"],
            cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_hwcheck_console.py", "-q",
         "-p", "no:cacheprovider", "-k", expression],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    lines: list[str] = [
        "# 工单 module-hwcheck/06 判据强度探针（停用守卫 → 用例必须变红）", "",
        "每条：注入故障 → 跑目标用例 → 期望**非零退出**（红）→ 逐字节复原。", "",
    ]
    # 前置干净性检查：注入前的目标文件必须逐字节等于"锚点唯一"的状态，否则说明
    # 上一轮被强杀、文件停在注入态（本仓库 2026-09-19 踩过）。
    originals: dict[str, str] = {}
    for _id, _desc, rel, _old, _new, _tests in MUTATIONS:
        if rel not in originals:
            originals[rel] = (REPO / rel).read_text(encoding="utf-8")
    dirty = [
        f"{ident}: {rel} 的锚点出现 {_anchor_count(rel, old, originals[rel])} 次（应为 1）"
        for ident, _desc, rel, old, _new, _tests in MUTATIONS
        if _anchor_count(rel, old, originals[rel]) != 1
    ]
    if dirty:
        lines.append("**前置检查失败**：锚点不唯一 / 文件疑似停在注入态——先复原再跑。")
        lines.extend(f"  - {item}" for item in dirty)
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 2

    failures = 0
    for ident, desc, rel, old, new, tests in MUTATIONS:
        path = REPO / rel
        original = originals[rel]
        restore_broken = False
        try:
            path.write_text(original.replace(old, new, 1), encoding="utf-8")
            code, output = _run(tests)
        finally:
            path.write_text(original, encoding="utf-8")
            restore_broken = path.read_text(encoding="utf-8") != original
        if restore_broken:
            lines.append(f"## {ident}：**复原失败**（{rel} 与原文不一致）")
            failures += 1
            continue
        red = code != 0
        if not red:
            failures += 1
            summary = "（**没红** = 这条守卫是摆设）"
        else:
            marks = re.findall(r"^FAILED (\S+)", output, re.MULTILINE)
            if not marks:  # node 侧：`✖ <用例名>`
                marks = re.findall(r"^✖ (.+?) \(\d", output, re.MULTILINE)
            summary = " / ".join(marks[:3]) or output.strip().splitlines()[-1][:120]
        lines.append(f"## {ident}：{'红 ✓' if red else '绿 ✗'} exit={code} {summary}")
        lines.append(f"  注入：{rel} —— {desc}")
        lines.append(f"  用例：{tests[0]} {tests[1] if len(tests) > 1 else ''}")
        lines.append("")
    lines.append("## 结论")
    lines.append(
        f"{len(MUTATIONS)} 条注入，{len(MUTATIONS) - failures} 条判红、"
        f"{failures} 条没红。"
        + ("每条守卫都真有牙。" if not failures else "**有守卫是摆设**。")
    )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
