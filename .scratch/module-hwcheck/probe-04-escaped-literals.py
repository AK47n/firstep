# -*- coding: utf-8 -*-
"""量具：**不依赖编译开关**的第二条路——把中文字面量写成 `\\xNN` 转义字节。

动机：`--locale=english` 能治 ARMCC（probe-04-armcc-flags.py 实测 0 error），
但它要求改**母版工程的编译开关**（跨平台共享面）。如果"把非 ASCII 字符转义成
UTF-8 字节"也能过，那就不必动母版——渲染器自己保证产物是纯 ASCII 源码即可。

本脚本对同一批必炸候选，分别用「原样 UTF-8」与「\\xNN 转义」写两个 .c，各真编译
一次（不加任何开关），并核对**转义版产出的字节**与原文 UTF-8 字节逐字节相等
（转义不能改变上网后看到的字）。

用法：python .scratch/module-hwcheck/probe-04-escaped-literals.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ARMCC = Path(r"C:\Keil5\Core\ARM\ARMCC\Bin\armcc.exe")

LITERALS: tuple[str, ...] = (
    "  通过：",
    "（灯闪 / 屏亮）",
    "检测程序开始跑。",
    "检测汇总",
    "led：初始化没有按接口约定返回期望值",
    "通信失败：先查供电 / 上拉 / 地址 / 线序，再查驱动",
)


def escape(text: str) -> str:
    """非 ASCII 字符 → UTF-8 字节的 \\xNN 转义（ASCII 字符原样保留）。"""
    out: list[str] = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
        else:
            out.extend(f"\\x{byte:02x}" for byte in ch.encode("utf-8"))
    return "".join(out)


def _compile(source: Path, out: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [str(ARMCC), "--c99", "-c", str(source), "-o", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    root = Path(tempfile.mkdtemp(prefix="firstep-escaped-"))
    lines = ["# 中文字面量：原样 UTF-8 vs \\xNN 转义（真 armcc，不加开关）", ""]
    try:
        raw_src = root / "raw.c"
        esc_src = root / "escaped.c"
        raw_src.write_text(
            "\n".join(
                f'const char *raw{i}(void) {{ return "{lit}"; }}'
                for i, lit in enumerate(LITERALS)
            ) + "\n",
            encoding="utf-8",
        )
        esc_src.write_text(
            "\n".join(
                f'const char *esc{i}(void) {{ return "{escape(lit)}"; }}'
                for i, lit in enumerate(LITERALS)
            ) + "\n",
            encoding="utf-8",
        )
        for label, path in (("原样 UTF-8", raw_src), ("\\xNN 转义", esc_src)):
            code, output = _compile(path, root / f"{path.stem}.o")
            errors = [ln.strip() for ln in output.splitlines()
                      if "error" in ln.lower()]
            lines.append(f"## {label} → 退出码 {code} / error {len(errors)}")
            for ln in errors[:6]:
                lines.append(f"  {ln[:150]}")
            lines.append("")
        ascii_only = all(byte < 128 for byte in esc_src.read_bytes())
        lines.append(f"转义版源码是纯 ASCII：{ascii_only}")
        same = all(
            escape(lit).encode("ascii").decode("unicode_escape").encode("latin-1")
            == lit.encode("utf-8")
            for lit in LITERALS
        )
        lines.append(
            f"转义产出的字节与原文 UTF-8 逐字节相等：{same}"
            "（判据：转义只是换个写法，上网后看到的字必须一模一样）"
        )
        lines.append("")
        lines.append("## 结论")
        lines.append(
            "转义版 0 error 且字节相等 → **渲染器把非 ASCII 转义掉**即可，"
            "不必改母版编译开关（跨平台共享面）。"
            if not ascii_only
            else "见上（转义版若仍报错，这条路走不通）。"
        )
        text = "\n".join(lines)
        print(text)
        (Path(__file__).resolve().parent
         / "probe-04-escaped-literals.txt").write_text(text + "\n", encoding="utf-8")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
