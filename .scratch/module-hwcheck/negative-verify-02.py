# -*- coding: utf-8 -*-
"""工单 module-hwcheck/02 判据强度探针：**停用每一条新守卫 → 对应用例必须变红**。

本仓库既有纪律（工单 01 Comments 同款）：新守卫不能只证明"现在是绿的"——还要
证明"坏了会红"。本脚本逐条注入故障、跑对应用例、记下红证，最后逐字节复原
（读原文 → 替换 → 跑 → 写回原文；任何一条没红都算探针失败）。

用法：python .scratch/module-hwcheck/negative-verify-02.py
输出：negative-verify-02.txt（每条：注入点 / 用例 / 退出码 / 红证摘要）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "negative-verify-02.txt"

# (编号, 说明, 相对路径, 原文片段, 注入片段, pytest 目标)
MUTATIONS: list[tuple[str, str, str, str, str, list[str]]] = [
    (
        "A",
        "stm32 头名回退成 mspm0 的名字（工单 01 的原缺陷）→ 平台过滤器与 include 用例应红",
        "src/contest_generator/hwcheck.py",
        '    PLATFORM_STM32: {\n        "entry": "headfile.h",\n        "serial": "debug_uart.h",\n        "oled": None,\n        "delay": None,',
        '    PLATFORM_STM32: {\n        "entry": "headfile.h",\n        "serial": "debug_uart.h",\n        "oled": "oled.h",\n        "delay": "delay.h",',
        ["tests/test_hwcheck.py", "-q", "-k", "include or stm32_does_not_include"],
    ),
    (
        "B",
        "目录名解析不再校验平台词表（赛题工程 / 瞎写的平台会被当检测工程）→ 扫描用例应红",
        "src/contest_generator/hwcheck_store.py",
        "    platform = match.group(\"platform\")\n    if platform not in KNOWN_PLATFORMS:\n        return None",
        "    platform = match.group(\"platform\")",
        ["tests/test_hwcheck_store.py", "-q", "-k", "rejects_foreign or scans_only"],
    ),
    (
        "C",
        "本地勾选态解码去掉坏值防护（JSON 坏了直接抛）→ 前端用例应红",
        "src/contest_generator/static/js/fx/hwcheck.js",
        "  try {\n    const parsed = JSON.parse(raw);\n    if (!Array.isArray(parsed)) return [];\n    return parsed.filter((id) => typeof id === \"string\");\n  } catch {\n    return [];\n  }",
        "  const parsed = JSON.parse(raw);\n  return parsed.filter((id) => typeof id === \"string\");",
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "D",
        "清单读侧不再把缺字段 / 未知值归一为赛题工程 → 上下文清单用例应红",
        "src/contest_generator/context_manifest.py",
        '        "kind": raw_kind if raw_kind in CONTEXT_KINDS else CONTEXT_KIND_CONTEST,',
        '        "kind": raw_kind,',
        ["tests/test_context_manifest.py", "-q", "-k", "kind"],
    ),
    (
        "E",
        "ui 手拼清单壳（不再走 fx 单源）→ 前端「不手拼壳」守卫应红",
        "src/contest_generator/static/js/ui/hwcheck.js",
        "  box.innerHTML = hwcheckChecklistProgressHTML(items, hwcheckUI.checklistChecked)\n    + hwcheckChecklistHTML(items, hwcheckUI.checklistChecked);",
        '  box.innerHTML = \'<label class="hwcheck-check">\' + items.length + "</label>";',
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "F",
        "mspm0 双通道「生成前会撞脚」的引导被拿掉 → 引导用例应红",
        "src/contest_generator/static/js/fx/hwcheck.js",
        '  if (platform !== "mspm0" || !debugUart || !oled) return "";',
        '  if (false) return "";',
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "G",
        "赛题侧（修订 / 深化）不再拒绝检测工程 → kind 消费点用例应红",
        "src/contest_generator/webapp.py",
        '        if fields["kind"] != CONTEXT_KIND_CONTEST:',
        "        if False:",
        ["tests/test_hwcheck.py", "-q", "-k", "revise_context_rejects"],
    ),
    (
        "H",
        "最近列表的 limit 不校验（非正整数照收）→ 查询参数用例应红",
        "src/contest_generator/webapp.py",
        "    if not text.isdigit() or int(text) < 1:\n"
        '        raise HwCheckError(f"limit 必须是正整数（一次列几条），收到 {raw!r}")',
        "    if not text.isdigit():\n        return 1",
        ["tests/test_hwcheck.py", "-q", "-k", "bad_limit"],
    ),
]


def run_node_test(target: str) -> list[str]:
    return ["node", "--test", target]


def run_pytest(args: list[str]) -> list[str]:
    return [sys.executable, "-m", "pytest", *args]


def main() -> int:
    lines: list[str] = ["# 工单 module-hwcheck/02 判据强度探针（停用守卫 → 必须变红）", ""]
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
                run_pytest(target) if target[0].endswith(".py")
                else run_node_test(target[0])
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
