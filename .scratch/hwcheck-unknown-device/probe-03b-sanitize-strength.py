# -*- coding: utf-8 -*-
"""hwcheck-unknown-device/03 附：**用户文本消毒**这条守卫的判据强度（反证）。

评审抓到的真缺陷：用户填的 `name` / `notes` 是自由文本，原先原样插进 C 块注释
——备注里一个 `*/` 就把注释提前闭合、后面整段变成语法错误。修复 = `_comment_text`
消毒（终结序列 + 换行 / 控制字符 + 收白 + 截断）。

本探针证的是"那条用例真的靠这个函数红"：把 `_comment_text` 改成恒等（= 回到
修复前）→ 用例必须红 → 逐字节复原 → 复核 sha256 → 复跑回绿。

用法：`python .scratch/hwcheck-unknown-device/probe-03b-sanitize-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "hwcheck_custom.py"
TEST = "tests/test_hwcheck_custom.py::test_user_text_never_breaks_the_c_comment"

NEEDLE = "    return cleaned[:_COMMENT_MAX_CHARS]\n"
PLANTED = (
    "    return str(text or \"\")  # [探针注入] 消毒被拿掉（反证用，跑完复原）\n"
)


def run_test() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", TEST],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, (text.strip().splitlines()[-1] if text.strip() else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    original = TARGET.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines: list[str] = []
    ok = text.count(NEEDLE) == 1

    if not ok:
        lines.append(f"[1] 前置检查失败：注入目标出现 {text.count(NEEDLE)} 次（应为 1）")
    else:
        lines.append(f"[1] 前置检查：sha256={digest[:32]}…，注入目标唯一 ✓")
        green, tail = run_test()
        lines.append(f"[2] 注入前（消毒在）：{'PASS' if green else 'FAIL'} ｜ {tail}")
        ok = ok and green

    if ok:
        TARGET.write_bytes(text.replace(NEEDLE, PLANTED).encode("utf-8"))
        try:
            green, tail = run_test()
            lines.append(
                f"[3] 注入后（消毒变恒等）："
                f"{'仍绿（守卫是摆设！）' if green else 'RED（用例变红）'} ｜ {tail}"
            )
            ok = ok and not green
        finally:
            TARGET.write_bytes(original)

    restored = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    lines.append(f"[4] 复原复核：sha256 {'相等 ✓' if restored == digest else '不等 ✗'}")
    ok = ok and restored == digest

    if restored == digest:
        green, tail = run_test()
        lines.append(f"[5] 复原后复跑：{'PASS（回绿）' if green else 'FAIL'} ｜ {tail}")
        ok = ok and green

    lines.append(f"结论：{'反证成立（消毒是那条用例变红的唯一判据）' if ok else '反证不成立 / 读数不完整'}")
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
