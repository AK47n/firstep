# -*- coding: utf-8 -*-
"""hwcheck-unknown-device/03 判据强度探针：**"调用集 ⊆ i2c_probe 接口"这条守卫真的会红**。

工单验收项：「反证：让渲染器多调一个不存在的函数，守卫用例必须变红（读数记进本工单）」。

做法照 `.scratch/hwcheck-unknown-device/probe-02-guard-strength.py` 的先例：

1. **前置干净性检查**：源文件必须与注入目标逐字匹配（强杀留下的注入态会让整份
   读数不可信）；
2. 注入：在 `hwcheck_custom.render_custom_section` 的产物里多插一句
   `i2c_probe_write_reg(...)`——一个**头文件里不存在**的函数（同时也是写侧调用）；
3. 跑对应用例，断言**必须变红**（两条判据各挡一半：调用集越界、产物里出现写调用）；
4. 逐字节复原 + sha256 复核 + 再跑一次（必须回绿）。

**别和测试套件同时跑**（仓库既有纪律：探针会真改库内文件）。

用法：`python .scratch/hwcheck-unknown-device/probe-03-guard-strength.py [--out FILE]`
先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "hwcheck_custom.py"

# 注入点 = 渲染器里 ping 之后那一行（锚点唯一、且插进去正好落在产物的小节里）
NEEDLE = '''    out.append(f"    r = i2c_probe_ping({address_text});")
'''
PLANTED = '''    out.append(f"    r = i2c_probe_ping({address_text});")
    out.append("    i2c_probe_write_reg(0x68, 0x75, 0x01);  /* [探针注入] 不存在的函数 */")
'''

# 三块判据里会被这行注入打红的两条 + 一条对照组（读侧白名单本身）
TESTS = [
    "tests/test_hwcheck_custom.py::test_every_called_name_exists_in_that_platforms_probe_header",
    "tests/test_hwcheck_custom.py::test_no_write_register_call_anywhere",
    "tests/test_hwcheck_custom.py::test_rendered_calls_are_only_the_read_side",
]


def run_tests() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TESTS],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    tail = text.strip().splitlines()[-1] if text.strip() else ""
    return proc.returncode == 0, tail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8；先落盘再打印）")
    args = parser.parse_args()

    original = TARGET.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines: list[str] = []
    ok = True

    if text.count(NEEDLE) != 1:
        lines.append(
            f"[1] 前置检查失败：注入目标出现 {text.count(NEEDLE)} 次（应为 1）"
            "——源文件不是预期形态，读数不可信"
        )
        ok = False
    else:
        lines.append(f"[1] 前置检查：源文件 sha256={digest[:32]}…，注入目标唯一 ✓")

    if ok:
        green, tail = run_tests()
        lines.append(f"[2] 注入前（守卫在）：{'PASS（全绿）' if green else 'FAIL'} ｜ {tail}")
        ok = ok and green

    if ok:
        TARGET.write_bytes(text.replace(NEEDLE, PLANTED).encode("utf-8"))
        try:
            green, tail = run_tests()
            lines.append(
                f"[3] 注入后（多调一个不存在的函数）："
                f"{'仍全绿（反证不成立！）' if green else 'RED（守卫用例变红）'} ｜ {tail}"
            )
            ok = ok and not green
        finally:
            TARGET.write_bytes(original)   # 无论上面发生什么都要复原

    restored = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    lines.append(
        f"[4] 复原复核：sha256 {'相等 ✓' if restored == digest else '不等 ✗'}（{restored[:32]}…）"
    )
    ok = ok and restored == digest

    if restored == digest:
        green, tail = run_tests()
        lines.append(f"[5] 复原后复跑：{'PASS（回绿）' if green else 'FAIL'} ｜ {tail}")
        ok = ok and green

    lines.append(
        f"结论：{'反证成立（多调一个不存在的函数 = 守卫当场变红）' if ok else '反证不成立 / 读数不完整'}"
    )
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")   # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
