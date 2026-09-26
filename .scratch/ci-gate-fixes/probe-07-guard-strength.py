#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe-07-guard-strength.py — 工单 ci-gate-fixes/07 的判据强度探针。

问的问题：改完之后的 `md-library.test.mjs::formatMtime` 那条断言**还有没有牙齿**？
做法：把产品侧实现临时换成"拿 UTC 取值"（这正是本单要防的那种错），在东八下跑该文件
——期望值按本地现算，所以只要实现真读错了时区，判据必须红。

纪律（照本仓先例）：探针会真改库内文件，**不许与测试套件同时跑**；读写逐字节保真，
跑完按 sha256 复核复原。读数先落盘再打印（本机控制台是 GBK，先 print 会让盘上那份丢）。
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "src" / "contest_generator" / "static" / "js" / "fx" / "md.js"
TEST = ROOT / "tests" / "js" / "md-library.test.mjs"

LOCAL_LINE = (
    "  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} "
    "${pad(d.getHours())}:${pad(d.getMinutes())}`;"
)
UTC_LINE = (
    "  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} "
    "${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_test(tz: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["TZ"] = tz
    proc = subprocess.run(
        ["node", "--test", str(TEST)],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    tail = [ln.strip() for ln in (proc.stdout + proc.stderr).splitlines()
            if ln.strip().startswith(("\u2139 fail", "\u2139 pass", "not ok"))]
    return proc.returncode, " | ".join(tail)


def main() -> int:
    before = sha256(TARGET)
    original = TARGET.read_bytes()
    src = original.decode("utf-8")
    if LOCAL_LINE not in src:
        print("[FAIL] 注入锚点没找到：产品侧 formatMtime 的 return 行变了？")
        return 2

    lines = []
    lines.append(f"目标文件: {TARGET.relative_to(ROOT)}")
    lines.append(f"注入前 sha256: {before}")

    # ① 基线（东八）：必须绿
    code_base, sum_base = run_test("Asia/Shanghai")
    lines.append(f"[基线 东八 未注入] exit={code_base} :: {sum_base}")

    # ② 注入"拿 UTC 取值" → 东八下必须红（判据有牙齿）
    try:
        TARGET.write_bytes(src.replace(LOCAL_LINE, UTC_LINE, 1).encode("utf-8"))
        code_inj, sum_inj = run_test("Asia/Shanghai")
        lines.append(f"[注入 UTC 取值 东八] exit={code_inj} :: {sum_inj}")
        code_inj_utc, sum_inj_utc = run_test("UTC")
        lines.append(f"[注入 UTC 取值 UTC ] exit={code_inj_utc} :: {sum_inj_utc}（对照：UTC 下这实现是对的，应当绿）")
    finally:
        TARGET.write_bytes(original)

    after = sha256(TARGET)
    lines.append(f"复原后 sha256: {after}")
    restored = after == before
    lines.append(f"逐字节复原: {'OK' if restored else 'MISMATCH'}")

    teeth = code_base == 0 and code_inj != 0 and code_inj_utc == 0 and restored
    lines.append(f"结论: {'[PASS] 判据有牙齿（东八下 UTC 取值必红，UTC 下同一实现绿）' if teeth else '[FAIL]'}")

    out = ROOT / ".scratch" / "ci-gate-fixes" / "probe-07-guard-strength.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    return 0 if teeth else 1


if __name__ == "__main__":
    raise SystemExit(main())
