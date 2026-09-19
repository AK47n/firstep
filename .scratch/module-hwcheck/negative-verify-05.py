# -*- coding: utf-8 -*-
"""工单 module-hwcheck/05 判据强度探针：**停用每一条新守卫 → 对应用例必须变红**。

本仓库既有纪律（工单 01/02/03/04 Comments 同款）：新守卫不能只证明"现在是绿的"
——还要证明"坏了会红"。本脚本逐条注入故障、跑对应用例、记下红证，最后逐字节复原
（读原文 → 替换 → 跑 → 写回原文；任何一条没红都算探针失败）。

本单的守卫集中在四类坏法：

① **探头不判通断**（期望值被改掉 / 探头段消失）——那正是"看着测了其实没测"；
② **引用的东西不存在**（大小写函数名绕过判据 / include 头名没判 / 局部变量名拼错）；
③ **产物编不过**（转义贪婪吃字符 / 器件头没 include / 死代码没过 0 warning）；
④ **平台不对称被抹平**（互斥组不按平台过滤 / mspm0 的 SysTick 垫片没了）。

用法：python .scratch/module-hwcheck/negative-verify-05.py
输出：negative-verify-05.txt（每条：注入点 / 用例 / 退出码 / 红证摘要）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "negative-verify-05.txt"

# (编号, 说明, 相对路径, 原文片段, 注入片段, 目标用例参数)
MUTATIONS: list[tuple[str, str, str, str, str, list[str]]] = [
    (
        "A",
        "**探头期望值被改错**（0x68 → 0x69）：板上判定跟着翻 FAIL，"
        "而断言「期望值进比较式」的用例必须红——票面点名的那条红证",
        "library/hwcheck_recipes.json",
        '"expect": "0x68"',
        '"expect": "0x69"',
        ["tests/test_hwcheck_recipe.py", "-q", "-k",
         "stm32_judges_comm or stm32_renders_a_self_proving"],
    ),
    (
        "B",
        "**器件头不再 include**（配方 include 段清空）：产物里 MPU6050 的调用变隐式"
        "声明（真机 7 error）→ 头文件用例与 include 解析用例必须红",
        "library/hwcheck_recipes.json",
        '"include": {\n        "headers": [\n          "ml_mpu6050.h",\n'
        '          "ml_i2c.h"\n        ]\n      },',
        '"include": {\n        "headers": []\n      },',
        ["tests/test_hwcheck.py", "-q", "-k",
         "bring_their_own_headers or mpu_section_includes_resolve"],
    ),
    (
        "C",
        "**局部变量名拼错**（pitch → pitchX）：读数表达式引用了没声明的变量 → "
        "真库配方校验必须红",
        "library/hwcheck_recipes.json",
        '"float pitch = 0",',
        '"float pitchX = 0",',
        ["tests/test_hwcheck_recipe.py", "-q", "-k", "mpu6050_recipes_pass"],
    ),
    (
        "D",
        "**大写函数名拼错**（DMP_Init → DMP_Initt）：判据必须拦住它（工单 05 修的"
        "漏洞：原先只查小写开头的标识符，官方库那些大写函数压根没过判据）",
        "library/hwcheck_recipes.json",
        '"DMP_Init()"',
        '"DMP_Initt()"',
        ["tests/test_hwcheck_recipe.py", "-q", "-k", "mpu6050_recipes_pass"],
    ),
    (
        "E",
        "**把大小写过滤加回 `_calls_in`**（历史写法）：上层那条 D 类拼错就再也拦不住"
        "→ 前置调用的拼错用例必须红",
        "src/contest_generator/hwcheck_recipe.py",
        "        if name in _C_KEYWORDS:\n            continue",
        "        if name in _C_KEYWORDS:\n            continue\n"
        "        if not (name[0].islower() or name[0] == '_'):\n            continue",
        ["tests/test_hwcheck_recipe.py", "-q", "-k",
         "prereq_segment_across_modules or does_not_declare"],
    ),
    (
        "F",
        "**转义退回贪婪的 `\\xNN`**：`±2g` 会被读成 `\\xb12`（越界转义）→ "
        "逐字节还原用例必须红",
        "src/contest_generator/hwcheck_recipe.py",
        '            out.extend(f"\\\\{byte:03o}" for byte in char.encode("utf-8"))',
        '            out.extend(f"\\\\x{byte:02x}" for byte in char.encode("utf-8"))',
        ["tests/test_hwcheck_recipe.py", "-q", "-k", "byte_exact_and_never_greedy"],
    ),
    (
        "G",
        "**死代码按需渲染失效**（`_needs_probe_none` 恒真）：整趟都是带判定探头时"
        "多留一个没人调的函数（真机 -Wunused-function）→ 0 warning 用例必须红",
        "src/contest_generator/hwcheck.py",
        "    return any(\n        not (section.probe and section.probe.expect) "
        "for section in sections\n    )",
        "    return True",
        ["tests/test_hwcheck.py", "-q", "-k", "full_probe_run_does_not_declare"],
    ),
    (
        "H",
        "**mspm0 的 SysTick 垫片没被渲染**（渲染点停用）：自己开 SysTick 中断的驱动会"
        "掉进启动文件的 Default_Handler 死循环 → 垫片用例必须红",
        "src/contest_generator/hwcheck.py",
        "    lines.extend(_PLATFORM_FILE_SCOPE[config.platform])",
        "    lines.extend(())",
        ["tests/test_hwcheck.py", "-q", "-k", "systick_service"],
    ),
    (
        "I",
        "**互斥组不再按平台过滤**（platform 传空 = 全平台视图）：stm32 上只剩一件的"
        "姿态组也会出卡（页面报一个不存在的互斥）→ 互斥载荷用例必须红",
        "src/contest_generator/webapp.py",
        "                for group in collect_exclusive_groups(\n"
        "                    list(by_slug.values()), platform=config.platform\n"
        "                )",
        "                for group in collect_exclusive_groups(\n"
        "                    list(by_slug.values())\n"
        "                )",
        ["tests/test_hwcheck.py", "-q", "-k", "platform_scoped_exclusive_groups"],
    ),
    (
        "J",
        "**局部变量不再声明**（渲染器漏掉 locals 那一行）：探头拿不到变量、读数表达式"
        "引用未声明名 → 声明在最前 + 双平台渲染用例必须红",
        "src/contest_generator/hwcheck_recipe.py",
        "    for declaration in section.locals:\n"
        '        out.append(f"    {declaration};")',
        "    for declaration in []:\n"
        '        out.append(f"    {declaration};")',
        ["tests/test_hwcheck.py", "-q", "-k",
         "local_declarations_before_every_action or mspm0_renders_dmp_init_probe"],
    ),
    (
        "K",
        "**include 的头名不再校验**：拼错的头名一路漏到生成期（配方层判据失效）→ "
        "头名拼错用例必须红",
        "src/contest_generator/hwcheck_recipe.py",
        "                for header in section.include:\n"
        "                    if header.lower() in platform_headers:\n"
        "                        continue",
        "                for header in section.include:\n"
        "                    if True:\n"
        "                        continue",
        ["tests/test_hwcheck_recipe.py", "-q", "-k",
         "include_that_is_not_in_the_library"],
    ),
]


def _run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args, "-p", "no:cacheprovider"],
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
        "# 工单 module-hwcheck/05 判据强度探针（停用守卫 → 用例必须变红）", "",
        "每条：注入故障 → 跑目标用例 → 期望**非零退出**（红）→ 逐字节复原。", "",
    ]
    # 前置干净性检查：注入前的目标文件必须逐字节等于"注入锚点能找到"的状态，
    # 否则说明上一轮被强杀、文件停在注入态（本仓库 2026-09-19 踩过）。
    originals: dict[str, str] = {}
    dirty: list[str] = []
    for _id, _desc, rel, old, _new, _tests in MUTATIONS:
        if rel in originals:
            continue
        text = (REPO / rel).read_text(encoding="utf-8")
        originals[rel] = text
    for _id, _desc, rel, old, _new, _tests in MUTATIONS:
        if originals[rel].count(old) != 1:
            dirty.append(f"{_id}: {rel} 的锚点出现 "
                         f"{originals[rel].count(old)} 次（应为 1）")
    if dirty:
        lines.append("**前置检查失败**：锚点不唯一 / 文件疑似停在注入态——"
                     "先复原再跑。")
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
        summary = ""
        if not red:
            failures += 1
            summary = "（**没红** = 这条守卫是摆设）"
        else:
            marks = re.findall(r"^FAILED (\S+)", output, re.MULTILINE)
            summary = " / ".join(marks[:3]) or output.strip().splitlines()[-1][:120]
        lines.append(f"## {ident}：{'红 ✓' if red else '绿 ✗'} "
                     f"exit={code} {summary}")
        lines.append(f"  注入：{rel} —— {desc}")
        lines.append(f"  用例：pytest {' '.join(tests)}")
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
