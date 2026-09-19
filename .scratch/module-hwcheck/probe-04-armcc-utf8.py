# -*- coding: utf-8 -*-
"""量具：ARMCC（UV4 的 V5.06）对 .c 里中文字符串字面量的容忍边界。

问题（工单 module-hwcheck/04 编译矩阵实测）：`hwcheck_report("  通过：");` 这类
**以全角标点结尾**的中文字面量报 `#8: missing closing quote`，而 `"上电：板子活着，
检测程序开始跑"`（同样含全角冒号、但后面还有汉字）不报。要么是"某个字节对 + 引号"
的问题，要么是别的。

本脚本用**真 armcc** 逐个候选做一次编译，把"哪一类收尾字符会炸"量出来——
判据是编译器说的，不是我们猜的。

用法：python .scratch/module-hwcheck/probe-04-armcc-utf8.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ARMCC = Path(r"C:\Keil5\Core\ARM\ARMCC\Bin\armcc.exe")

# 候选字面量：全角标点 / 汉字 / 混排 / 长短，一一测过
CASES: tuple[tuple[str, str], ...] = (
    ("全角冒号结尾", "  通过："),
    ("全角逗号结尾", "  未判定，"),
    ("全角括号结尾", "（灯闪 / 屏亮）"),
    ("句号结尾", "检测程序开始跑。"),
    ("汉字结尾", "检测汇总"),
    ("等号结尾", "==== 检测汇总 ===="),
    ("全角括号 + 汉字", "（排查线索）汇总"),
    ("中间含全角括号", "先查供电 / 上拉（再查驱动）"),
    ("短全角", "项——这些件"),
    ("ASCII 结尾", "  init: "),
    ("汉字 + 全角冒号", "led：初始化"),
    ("全角冒号 + 汉字", "：初始化"),
)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    if not ARMCC.is_file():
        print(f"armcc 不在 {ARMCC}：本机没有 Keil ARMCC，量不了")
        return 1
    root = Path(tempfile.mkdtemp(prefix="firstep-armcc-utf8-"))
    lines = ["# ARMCC 中文字符串字面量容忍边界（逐个真编译）", ""]
    bad: list[str] = []
    try:
        for index, (label, literal) in enumerate(CASES):
            source = root / f"case{index:02d}.c"
            source.write_text(
                "const char *probe(void)\n{\n"
                f'    return "{literal}";\n'
                "}\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [str(ARMCC), "--c99", "-c", str(source), "-o",
                 str(root / f"case{index:02d}.o")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            problem = [ln.strip() for ln in output.splitlines()
                       if "error" in ln.lower() or "warning" in ln.lower()]
            verdict = "OK" if proc.returncode == 0 and not problem else "FAIL"
            if verdict == "FAIL":
                bad.append(label)
            lines.append(f"## {label}：{literal!r} → {verdict}（退出码 {proc.returncode}）")
            for ln in problem[:4]:
                lines.append(f"  {ln[:160]}")
            lines.append("")
        lines.append("## 结论")
        lines.append(
            f"{len(CASES)} 个候选，{len(bad)} 个报错：{'、'.join(bad) if bad else '（无）'}"
        )
        text = "\n".join(lines)
        print(text)
        (Path(__file__).resolve().parent / "probe-04-armcc-utf8.txt").write_text(
            text + "\n", encoding="utf-8"
        )
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
