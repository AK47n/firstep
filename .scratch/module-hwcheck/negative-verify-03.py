# -*- coding: utf-8 -*-
"""工单 module-hwcheck/03 判据强度探针：**停用每一条新守卫 → 对应用例必须变红**。

本仓库既有纪律（工单 01/02 Comments 同款）：新守卫不能只证明"现在是绿的"——还要
证明"坏了会红"。本脚本逐条注入故障、跑对应用例、记下红证，最后逐字节复原
（读原文 → 替换 → 跑 → 写回原文；任何一条没红都算探针失败）。

本单的守卫集中在两类坏法：
① **单源被拆成两处推导**（接线行不再照抄接线快照 / 冲突不再用既有分类 /
   顺序不再用既有排序）——那正是这次要防的漂移；
② **如实呈现被抹掉**（板上共享注记、缺平台条目、冲突 ⚠）——页面看起来照常，
   但学生拿到的是半个真相。

用法：python .scratch/module-hwcheck/negative-verify-03.py
输出：negative-verify-03.txt（每条：注入点 / 用例 / 退出码 / 红证摘要）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "negative-verify-03.txt"

# (编号, 说明, 相对路径, 原文片段, 注入片段, 目标用例)
MUTATIONS: list[tuple[str, str, str, str, str, list[str]]] = [
    (
        "A",
        "接线行不再照抄接线快照的推导（自己另排一遍）→ 与 README 逐格对比用例应红",
        "src/contest_generator/hwcheck_board.py",
        "        for row in wiring_rows(platform, manifests)\n    )",
        "        for row in sorted(wiring_rows(platform, manifests), key=lambda r: r[\"pin\"])\n    )",
        ["tests/test_hwcheck_board.py", "-q", "-k", "readme_pin_table or verbatim"],
    ),
    (
        "B",
        "板上共享注记被丢掉（PA0/PA1 的板载 LED 共用不再呈现）→ 暗雷用例应红",
        "src/contest_generator/hwcheck_board.py",
        '        {**row, "pin_note": pin_notes.get(row["pin"], "")}',
        '        {**row, "pin_note": ""}',
        ["tests/test_hwcheck_board.py", "-q", "-k", "onboard_led or pin_note"],
    ),
    (
        "C",
        "同脚组不再用既有分类（一律当合法共享）→ 冲突用例与分类同源用例应红",
        "src/contest_generator/hwcheck_board.py",
        "        groups=_shared_groups(manifests, platform, board, {}),",
        "        groups=tuple(\n"
        "            {**g, \"kind\": \"share\"}\n"
        "            for g in _shared_groups(manifests, platform, board, {})\n"
        "        ),",
        ["tests/test_hwcheck_board.py", "-q", "-k", "different_peripherals or existing_classifier"],
    ),
    (
        "D",
        "建议顺序不再走既有 bring-up 排序（按输入原序）→ 顺序用例应红",
        "src/contest_generator/hwcheck_board.py",
        "        for manifest in sort_verification_order(manifests)",
        "        for manifest in manifests",
        ["tests/test_hwcheck_board.py", "-q", "-k", "readme_verification_order or bring_up"],
    ),
    (
        "E",
        "缺平台条目的判据被掐掉（缺条目器件静默消失）→ 点名用例应红",
        "src/contest_generator/hwcheck_board.py",
        "        if warning.kind == WARNING_MISSING",
        "        if False",
        ["tests/test_hwcheck_board.py", "-q", "-k", "without_a_platform_entry or warning_table"],
    ),
    (
        "F",
        "回读不再取清单里的器件（刷新后器件选择丢失）→ 回读用例应红",
        "src/contest_generator/hwcheck_store.py",
        '        devices=tuple(fields["devices"]),',
        "        devices=(),",
        ["tests/test_hwcheck.py", "-q", "-k", "restores_the_device_selection"],
    ),
    (
        "G",
        "生成时不再把器件写进上下文清单 → 清单透传用例应红",
        "src/contest_generator/context_manifest.py",
        "    if devices is not None:\n        fields[\"devices\"] = list(devices)",
        "    if False:\n        fields[\"devices\"] = list(devices)",
        ["tests/test_context_manifest.py", "-q", "-k", "devices"],
    ),
    (
        "H",
        "选中器件不再进模块集（接线表与工程 README 分道）→ 模块集用例应红",
        "src/contest_generator/hwcheck.py",
        "    for slug in hwcheck_devices(config):\n"
        "        if slug not in modules:\n"
        "            modules.append(slug)",
        "    for slug in ():\n"
        "        if slug not in modules:\n"
        "            modules.append(slug)",
        ["tests/test_hwcheck.py", "-q", "-k", "selected_devices_join"],
    ),
    (
        "I",
        "冲突标记被抹平（⚠ 不再标）→ 前端冲突用例应红",
        "src/contest_generator/static/js/fx/hwcheck.js",
        '    const conflict = (group && group.kind) === "conflict";',
        "    const conflict = false;",
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "J",
        "接线行不再带板上共享标记 → 前端接线表用例应红",
        "src/contest_generator/static/js/fx/hwcheck.js",
        '      + (note ? `<span class="hwcheck-share">⚠ 板载共享：${esc(note)}</span>` : "")',
        '      + ""',
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "K",
        "生成 / 预览请求体不再带器件（选了不生效）→ 前端载荷用例应红",
        "src/contest_generator/static/js/fx/hwcheck.js",
        "    oled: !!state.oled,\n    devices: hwcheckDeviceSlugs(state),\n    parent_dir:",
        "    oled: !!state.oled,\n    parent_dir:",
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "L",
        "板载共享不再投影（板载 LED 同脚这类板上事实从冲突区消失）→ 板上共享用例应红",
        "src/contest_generator/hwcheck_board.py",
        "        board_shares=_board_shares(rows),",
        "        board_shares=(),",
        ["tests/test_hwcheck_board.py", "-q", "-k", "board_shares"],
    ),
    (
        "M",
        "板上共享不再渲染（页面又只剩「没有抢同一个引脚」的假安心）→ 前端用例应红",
        "src/contest_generator/static/js/fx/hwcheck.js",
        "  const list = Array.isArray(boardShares) ? boardShares : [];\n"
        '  if (!list.length) return "";',
        '  const list = [];\n  if (!list.length) return "";',
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "N",
        "在途触发不再排队重跑（连点两件器件会丢掉最后一次选择）→ 并发纪律守卫应红",
        "src/contest_generator/static/js/ui/hwcheck.js",
        "    if (hwcheckViewPending) {\n"
        "      hwcheckViewPending = false;\n"
        "      await refreshHwcheckView();",
        "    if (false) {\n"
        "      hwcheckViewPending = false;\n"
        "      await refreshHwcheckView();",
        ["tests/js/hwcheck.test.mjs"],
    ),
]


def main() -> int:
    # 控制台按 UTF-8 + errors=replace 输出：子进程红证里可能夹着解码替换符
    # （探针自己打印时不该因为控制台代码页炸掉——本机控制台默认 GBK）
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    lines: list[str] = ["# 工单 module-hwcheck/03 判据强度探针（停用守卫 → 必须变红）", ""]
    failed_probes: list[str] = []
    for tag, why, rel, old, new, target in MUTATIONS:
        path = REPO / rel
        original = path.read_text(encoding="utf-8")
        if old not in original:
            lines.append(f"## {tag} 注入点找不到（文件漂移？）：{rel}")
            failed_probes.append(tag)
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            command = (
                [sys.executable, "-m", "pytest", *target]
                if target[0].endswith(".py")
                else ["node", "--test", target[0]]
            )
            proc = subprocess.run(
                command, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=600,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            lines.append(f"## {tag} {why}")
            lines.append(f"注入：{rel}")
            lines.append(f"命令：{' '.join(command)}")
            lines.append(f"退出码：{proc.returncode}（判据要求非 0）")
            red = [ln for ln in output.splitlines()
                   if re.search(r"(FAILED|✖|AssertionError|failed)", ln)]
            lines.append("红证摘要：")
            lines.extend(f"  {ln.strip()[:200]}" for ln in red[:12])
            lines.append("")
            if proc.returncode == 0:
                failed_probes.append(tag)
        finally:
            path.write_text(original, encoding="utf-8")
    lines.append("## 结论")
    if failed_probes:
        lines.append(f"**探针失败**：注入后仍全绿的有 {failed_probes}（守卫没在守）")
    else:
        lines.append(f"全部 {len(MUTATIONS)} 条注入都按预期变红，且文件已逐字节复原。")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[已写入] {OUT}")
    return 1 if failed_probes else 0


if __name__ == "__main__":
    raise SystemExit(main())
