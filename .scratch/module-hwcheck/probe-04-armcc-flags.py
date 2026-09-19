# -*- coding: utf-8 -*-
"""量具：让 ARMCC 5.06 正确接受 UTF-8 中文字符串字面量的**最小改动**。

背景（probe-04-armcc-utf8.py 实测）：默认调用下，中文字面量常被 ARMCC 按本地
多字节代码页（本机 GBK）配对解析，把收尾引号当成前一个字节的前导字节吞掉 →
`#8: missing closing quote`，整份 main.c 编不过。

本脚本对同一批"必炸"候选逐个试三组编译开关，看哪一组能让它们全过：

* `--locale=english`（单字节本地化：不把字节按 GBK 配对）
* `--multibyte_chars=utf8`（显式声明源文件多字节编码）
* 两者都不加（对照，预期全炸）

用法：python .scratch/module-hwcheck/probe-04-armcc-flags.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ARMCC = Path(r"C:\Keil5\Core\ARM\ARMCC\Bin\armcc.exe")

# 上一支量具里"必炸"的收尾形态（每个都真炸过，不是构造的）
LITERALS: tuple[str, ...] = (
    "  通过：",
    "（灯闪 / 屏亮）",
    "检测程序开始跑。",
    "检测汇总",
    "led：初始化没有按接口约定返回期望值",
    "通信失败：先查供电 / 上拉 / 地址 / 线序，再查驱动",
)

FLAG_SETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("对照组（不加开关）", ()),
    ("--locale=english", ("--locale=english",)),
    ("--multibyte_chars=utf8", ("--multibyte_chars=utf8",)),
    ("两者都加", ("--locale=english", "--multibyte_chars=utf8")),
)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    if not ARMCC.is_file():
        print(f"armcc 不在 {ARMCC}：量不了")
        return 1
    root = Path(tempfile.mkdtemp(prefix="firstep-armcc-flags-"))
    lines = ["# 让 ARMCC 吃下 UTF-8 中文字面量的最小开关（真编译，逐个试）", ""]
    try:
        source = root / "probe.c"
        body = ["/* 逐个候选在函数里返回，模拟渲染产物里'参数位置'的中文字面量 */"]
        for index, literal in enumerate(LITERALS):
            body.append(
                f"const char *probe{index:02d}(void) {{ return \"{literal}\"; }}"
            )
        source.write_text("\n".join(body) + "\n", encoding="utf-8")
        for label, flags in FLAG_SETS:
            proc = subprocess.run(
                [str(ARMCC), "--c99", *flags, "-c", str(source), "-o",
                 str(root / "probe.o")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            problems = [ln.strip() for ln in output.splitlines()
                        if "error" in ln.lower()]
            lines.append(
                f"## {label} → 退出码 {proc.returncode} / "
                f"error {len(problems)} / warning "
                f"{len([ln for ln in output.splitlines() if 'warning' in ln.lower()])}"
            )
            for ln in problems[:6]:
                lines.append(f"  {ln[:150]}")
            lines.append("")
        lines.append("## 结论")
        lines.append("以上每组都对同一批 6 个中文字面量做了真编译——哪一组 0 error，")
        lines.append("就是生成侧该用的开关（没有 0 error 的组 = 这条路走不通，")
        lines.append("得改成'生成程序里不出现中文串'）。")
        text = "\n".join(lines)
        print(text)
        (Path(__file__).resolve().parent / "probe-04-armcc-flags.txt").write_text(
            text + "\n", encoding="utf-8"
        )
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
