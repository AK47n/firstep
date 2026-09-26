#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe-07-guard-strength.py — 工单 ci-gate-fixes/07 的判据强度探针。

问的问题：`md-library.test.mjs::formatMtime` 那条断言在**改成按本机时区现算之后**
还有没有牙齿？做法：把产品侧实现临时换成"拿 UTC 取值"（本单要防的那类错），在东八下跑该文件
——期望值按本地现算，所以只要实现真读错了时区，判据必须红；UTC 下同一注入应当**绿**
（那里本地与 UTC 行为相同，没有可区分的差——这条对照本身就是"牙齿长在哪一侧"的证据）。

纪律（照本仓先例）：
- 会真改库内文件，**不许与测试套件同时跑**；
- 读写逐字节保真，跑完按 sha256 复核复原；
- **前置干净性检查**：源文件若停在上一轮的注入态（被强杀过），本探针**拒绝跑**并说清
  怎么恢复——不然它会把"上次没收拾干净"误报成"产品实现变了"；
- 读数**先落盘再打印**（本机控制台是 GBK，先 print 会让盘上那份丢）；落点可 `--out` 指定。
"""
import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "src" / "contest_generator" / "static" / "js" / "fx" / "md.js"
TEST = ROOT / "tests" / "js" / "md-library.test.mjs"
DEFAULT_OUT = ROOT / ".scratch" / "ci-gate-fixes" / "probe-07-guard-strength.txt"

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
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)

    before = sha256(TARGET)
    original = TARGET.read_bytes()
    src = original.decode("utf-8")

    # 前置干净性检查：既不是"干净态"也不是"本探针的注入态" → 说不清是什么，别动它。
    has_local, has_utc = LOCAL_LINE in src, UTC_LINE in src
    if not has_local and has_utc:
        print("[FAIL] 源文件停在**上一轮的注入态**（UTC 取值），本探针拒绝跑。")
        print(f"       恢复：git -C {ROOT} checkout -- "
              f"{TARGET.relative_to(ROOT).as_posix()}")
        return 3
    if not has_local:
        print("[FAIL] 注入锚点没找到（且不是本探针的注入态）——产品侧 formatMtime 的"
              " return 行写法变了？先人工看一眼。")
        return 2

    lines = [
        f"目标文件: {TARGET.relative_to(ROOT)}",
        f"注入前 sha256: {before}",
    ]

    # ① 基线（东八）：必须绿
    code_base, sum_base = run_test("Asia/Shanghai")
    lines.append(f"[基线 东八 未注入] exit={code_base} :: {sum_base}")

    # ② 注入"拿 UTC 取值" → 东八下必须红（判据有牙齿）
    try:
        TARGET.write_bytes(src.replace(LOCAL_LINE, UTC_LINE, 1).encode("utf-8"))
        code_inj, sum_inj = run_test("Asia/Shanghai")
        lines.append(f"[注入 UTC 取值 东八] exit={code_inj} :: {sum_inj}")
        code_inj_utc, sum_inj_utc = run_test("UTC")
        lines.append(
            f"[注入 UTC 取值 UTC ] exit={code_inj_utc} :: {sum_inj_utc}"
            "（对照：UTC 下本地与 UTC 行为相同、无可区分差，应当绿——牙齿长在非 UTC 一侧）")
    finally:
        TARGET.write_bytes(original)

    after = sha256(TARGET)
    lines.append(f"复原后 sha256: {after}")
    restored = after == before
    lines.append(f"逐字节复原: {'OK' if restored else 'MISMATCH'}")

    teeth = code_base == 0 and code_inj != 0 and code_inj_utc == 0 and restored
    lines.append(
        "结论: " + ("[PASS] 东八下 UTC 取值必红；UTC 下同一实现绿（对照成立）"
                     if teeth else "[FAIL]"))

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    print(f"\n读数已落盘：{out.relative_to(ROOT)}")
    return 0 if teeth else 1


if __name__ == "__main__":
    raise SystemExit(main())
