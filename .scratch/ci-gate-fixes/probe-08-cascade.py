#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe-08-cascade.py — 工单 ci-gate-fixes/08 的**级联**红证。

问的问题：CI 上 `hwcheck.spec.mjs` 的三条红里，`:818`（自建件的串口复测）与 `:914`
（装不下时的出路）到底是不是被"上一条没清干净"拖下水的？

做法：把夹具的 `clearDevices()` 变成空操作（= **模拟 CI 上那次 `[afterEach] 器件集未清干净`
的后果**：选择集带着上一件的器件进下一条），跑同一支 spec，看红的是不是同一批用例、
红的形态是不是同一种（等预览载荷的 30 秒超时）。

对照：本机（有工具链）不注入时该 spec 21/21 全绿；无工具链时只红 `:398` 那条编译用例
（读数见同目录 `probe-08-*.txt`）。所以"注入后多红的那些"就是级联出来的。

纪律：会真改测试文件，**不许与测试套件同时跑**；逐字节读写 + sha256 复核复原；
读数先落盘再打印。
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "tests" / "browser" / "hwcheck.spec.mjs"
DEFAULT_OUT = ROOT / ".scratch" / "ci-gate-fixes" / "probe-08-cascade.txt"

ANCHOR_RE = re.compile(r"async function clearDevices\(\) \{(\r?\n)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_spec() -> tuple[int, list[str]]:
    proc = subprocess.run(
        ["node", "--test", "--test-concurrency=1", str(TARGET)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = proc.stdout + proc.stderr
    results = [re.sub(r"\s+", " ", ln.strip()) for ln in text.splitlines()
               if re.match(r"^\s*(✔|✖)\s", ln)]
    footer = [ln.strip() for ln in text.splitlines()
              if ln.strip().startswith(("\u2139 pass", "\u2139 fail", "\u2139 tests",
                                        "\u2139 skipped"))]
    return proc.returncode, results + ["---"] + footer


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)

    before = sha256(TARGET)
    original = TARGET.read_bytes()
    src = original.decode("utf-8")

    if "[DEBUG-c8f1]" in src:
        print("[FAIL] 测试文件停在**上一轮的注入态**，本探针拒绝跑。"
              "恢复：git checkout -- tests/browser/hwcheck.spec.mjs")
        return 3
    m = ANCHOR_RE.search(src)
    if not m:
        print("[FAIL] 锚点没找到（clearDevices 变了？）——先人工看一眼。")
        return 2
    eol = m.group(1)                      # 跟着**原文件的行尾**走（本工作树是 CRLF）
    anchor = m.group(0)
    inject = anchor + "  if (true) return;  // [DEBUG-c8f1] 注入：模拟 CI 那次清不干净" + eol

    lines = [f"目标文件: {TARGET.relative_to(ROOT)}", f"注入前 sha256: {before}", ""]
    try:
        TARGET.write_bytes(src.replace(anchor, inject, 1).encode("utf-8"))
        code, results = run_spec()
        lines.append(f"[注入：afterEach 清不干净] exit={code}")
        lines.extend(results)
    finally:
        TARGET.write_bytes(original)
        # 收尾：把注入态的残留文件清掉不影响 sha256 复核（下面按原字节写回）
    after = sha256(TARGET)
    lines.append("")
    lines.append(f"复原后 sha256: {after}")
    lines.append(f"逐字节复原: {'OK' if after == before else 'MISMATCH'}")

    reds = [r for r in results if r.startswith("\u2716")]
    cascade = len(reds) >= 2
    lines.append("结论: " + (
        "[PASS] 清不干净会级联出多条红（级联链成立）" if cascade and after == before
        else "[FAIL] 没级联出多条红——那 CI 上那两条就不是这条链，另行定性"))

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    print(f"\n读数已落盘：{out.relative_to(ROOT)}")
    return 0 if (cascade and after == before) else 1


if __name__ == "__main__":
    raise SystemExit(main())
