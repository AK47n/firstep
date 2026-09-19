# -*- coding: utf-8 -*-
"""工单 module-hwcheck/04 判据强度探针：**停用每一条新守卫 → 对应用例必须变红**。

本仓库既有纪律（工单 01/02/03 Comments 同款）：新守卫不能只证明"现在是绿的"——
还要证明"坏了会红"。本脚本逐条注入故障、跑对应用例、记下红证，最后逐字节复原
（读原文 → 替换 → 跑 → 写回原文；任何一条没红都算探针失败）。

本单的守卫集中在两类坏法：

① **配方引用的东西不真**（函数名不在接口清单里却放行 / 空壳配方放行 / 期望值
   拼错常量名放行）——那正是 spec 说的"看着测了其实没测"；
② **"不假装测过"被抹掉**（没探头的件被算进通过 / 未专精点名消失 / 专精标记
   消失 / 逐件小节根本没被 main 调用）。

用法：python .scratch/module-hwcheck/negative-verify-04.py
输出：negative-verify-04.txt（每条：注入点 / 用例 / 退出码 / 红证摘要）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "negative-verify-04.txt"

# (编号, 说明, 相对路径, 原文片段, 注入片段, 目标用例)
MUTATIONS: list[tuple[str, str, str, str, str, list[str]]] = [
    (
        "A",
        "配方引用的函数名不再校验（写错的接口名一路走到板上）→ 核心守卫用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        "                    for name in _calls_in(expression):\n"
        "                        if name not in known:",
        "                    for name in _calls_in(expression):\n"
        "                        if False:",
        ["tests/test_hwcheck_recipe.py", "-q", "-k",
         "does_not_declare or read_and_probe_segments"],
    ),
    (
        "B",
        "期望值不再校验常量名（expect 里拼错的宏名一路进比较式）→ 期望值用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        "                for name in _bare_names(expect):\n"
        "                    if name not in known:",
        "                for name in _bare_names(expect):\n"
        "                    if False:",
        ["tests/test_hwcheck_recipe.py", "-q", "-k",
         "neither_literal_nor_interface or names_an_interface_constant"],
    ),
    (
        "C",
        "空壳配方放行（六段全空也算「专精」，学生以为这件被测过）→ 空壳用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        "    if not section.usable:",
        "    if False:",
        ["tests/test_hwcheck_recipe.py", "-q", "-k", "empty_recipe"],
    ),
    (
        "D",
        "探头段不再要求 expect 是字符串（数字也能过）→ 探头形状用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        "            if not isinstance(raw, str):\n"
        "                raise HwCheckError(\n"
        '                    f"{probe_where}的 probe.expect 必须是字符串，收到 {raw!r}"',
        "            if False:\n"
        "                raise HwCheckError(\n"
        '                    f"{probe_where}的 probe.expect 必须是字符串，收到 {raw!r}"',
        ["tests/test_hwcheck_recipe.py", "-q", "-k", "bad_expect_type"],
    ),
    (
        "E",
        "接口清单为空时不再宽免（只配模块库、没配母版库的场景被误判成配方坏）→ "
        "端点预览用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        "            if not known:",
        "            if False:",
        ["tests/test_hwcheck.py", "-q", "-k",
         "preview_endpoint_returns_main_c or honours_channel_flags"],
    ),
    (
        "F",
        "专精小节不再被 main() 调用（渲染了却没人跑 = 白渲染）→ 小节调用用例应红",
        "src/contest_generator/hwcheck.py",
        '            lines.append(f"    hwcheck_check_{section.slug}();")',
        "            pass",
        ["tests/test_hwcheck.py", "-q", "-k",
         "add_their_calls or writes_the_specialized_sections"],
    ),
    (
        "G",
        "没有探头的件不再记账（与「通过」混为一谈 / 未判定永远数出 0）→ 三档分账用例应红",
        "src/contest_generator/hwcheck.py",
        '        "    hwcheck_summary_probe_none++;",',
        '        "    /* 注入：不记账 */",',
        ["tests/test_hwcheck.py", "-q", "-k", "three_buckets"],
    ),
    (
        "H",
        "专精标记被抹平（专精件与未专精件外观不再可区分）→ 外观用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        'SECTION_TAG = "[专精]"',
        'SECTION_TAG = ""',
        ["tests/test_hwcheck.py", "-q", "-k",
         "visually_distinct or add_their_calls"],
    ),
    (
        "I",
        "小节顺序不再走既有 bring-up 排序（检测程序与 README 清单打脸）→ 顺序用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        "    return tuple(\n        sorted(\n"
        "            (section for section in sections if section is not None),\n"
        "            key=lambda section: (order.get(section.slug, len(order)), section.slug),\n"
        "        )\n    )",
        "    return tuple(\n"
        "        reversed(sorted(\n"
        "            (section for section in sections if section is not None),\n"
        "            key=lambda section: (order.get(section.slug, len(order)), section.slug),\n"
        "        ))\n"
        "    )",
        ["tests/test_hwcheck_recipe.py", "-q", "-k",
         "verification_order or skips_devices_without_a_recipe"],
    ),
    (
        "J",
        "未专精件不再点名（选了却没配方 = 静默消失）→ 点名用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        "    return (\n"
        '        f"{slug}：这一件还没有专精配方——本版检测程序不会给它出检测小节"',
        "    return (\n"
        '        f""',
        ["tests/test_hwcheck.py", "-q", "-k", "without_a_recipe_as_unspecialized"],
    ),
    (
        "K",
        "前端不再标「只看现象」（没探头的件看起来像测过了）→ 前端判定档位用例应红",
        "src/contest_generator/static/js/fx/hwcheck.js",
        "    const probeBadge = s.has_probe\n"
        "      ? '<span class=\"badge ok\">板上判定</span>'\n"
        "      : '<span class=\"badge\">只看现象</span>';",
        "    const probeBadge = '';",
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "L",
        "前端不再点名未专精件（选了没配方的件静默消失）→ 前端点名用例应红",
        "src/contest_generator/static/js/fx/hwcheck.js",
        "  const list = Array.isArray(items) ? items : [];\n"
        '  if (!list.length) return "";',
        "  const list = [];\n"
        '  if (!list.length) return "";',
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "M",
        "换平台 / 换通道不再清旧检测计划（旧平台的配方留在页面上误导）→ 清计划用例应红",
        "src/contest_generator/static/js/ui/hwcheck.js",
        "        hwcheckUI.sections = [];          // 换板 = 旧检测计划作废（配方按平台分）",
        "        /* 注入：不清 */",
        ["tests/js/hwcheck.test.mjs"],
    ),
    (
        "N",
        "中文字面量不再转义（原样写进 C → ARMCC 报 #8 编不过）→ 结构守卫应红",
        "src/contest_generator/hwcheck_recipe.py",
        '            out.extend(f"\\\\x{byte:02x}" for byte in char.encode("utf-8"))',
        "            out.append(char)",
        ["tests/test_hwcheck.py", "-q", "-k", "raw_non_ascii"],
    ),
    (
        "O",
        "判不了返回值的件也硬渲判定函数（留死代码 / 编出 #177-D）→ 死代码守卫应红",
        "src/contest_generator/hwcheck.py",
        "    return any(\n"
        "        section.init_expect or (section.probe and section.probe.expect)\n"
        "        for section in sections\n"
        "    )",
        "    return True",
        ["tests/test_hwcheck.py", "-q", "-k", "dead_helpers"],
    ),
    (
        "P",
        "读数表达式里的裸常量不再查（跨平台常量漏到编译期）→ 裸常量判据用例应红",
        "src/contest_generator/hwcheck_recipe.py",
        "                    for name in _bare_names(expression):\n"
        "                        if name in _C_KEYWORDS or name in known:\n"
        "                            continue",
        "                    for name in ():\n"
        "                        if name in _C_KEYWORDS or name in known:\n"
        "                            continue",
        ["tests/test_hwcheck_recipe.py", "-q", "-k", "read_and_probe_segments"],
    ),
]


def main() -> int:
    # 控制台按 UTF-8 + errors=replace 输出：子进程红证里可能夹着解码替换符
    # （探针自己打印时不该因为控制台代码页炸掉——本机控制台默认 GBK）
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    lines: list[str] = [
        "# 工单 module-hwcheck/04 判据强度探针（停用守卫 → 必须变红）", ""
    ]
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
