#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe-08-diag-redproof.py — 工单 ci-gate-fixes/08 的**诊断红证**。

问的问题：`:818` 那处（自建件的串口复测）新加的失败诊断到底会不会真的打印出
"接线区 / 命令台 / 末几次 preview 响应"？——没被看见触发过的诊断不算证据。

做法：把该处 `waitForSelector` 的**选择器**改成一个不存在的**（其余一字不动）**，
跑该 spec：这一条必须红，且红信息里必须同时出现三段 `[诊断]`。

纪律：逐字节读写 + sha256 复核复原；读数先落盘再打印。
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "tests" / "browser" / "hwcheck.spec.mjs"
DEFAULT_OUT = ROOT / ".scratch" / "ci-gate-fixes" / "probe-08-diag-redproof.txt"

GOOD = '    await page.waitForSelector("#hwcheck-console .hwcheck-table");'
BAD = '    await page.waitForSelector("#hwcheck-console .no-such-table-for-probe");'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)

    before = sha256(TARGET)
    original = TARGET.read_bytes()
    src = original.decode("utf-8")

    if ".no-such-table-for-probe" in src:
        print("[FAIL] 测试文件停在上一轮的注入态，本探针拒绝跑。"
              "恢复：git checkout -- tests/browser/hwcheck.spec.mjs")
        return 3
    if src.count(GOOD) != 1:
        print(f"[FAIL] 锚点不是恰好一处（实际 {src.count(GOOD)} 处）——先人工看一眼。")
        return 2

    lines = [f"目标文件: {TARGET.relative_to(ROOT)}", f"注入前 sha256: {before}", ""]
    try:
        TARGET.write_bytes(src.replace(GOOD, BAD, 1).encode("utf-8"))
        proc = subprocess.run(
            ["node", "--test", "--test-concurrency=1", str(TARGET)],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        text = proc.stdout + proc.stderr
        diag_lines = [ln.strip() for ln in text.splitlines() if "[诊断]" in ln]
        red = [ln.strip() for ln in text.splitlines()
               if re.match(r"^\s*\u2716\s", ln)]
        footer = [ln.strip() for ln in text.splitlines()
                  if ln.strip().startswith(("\u2139 pass", "\u2139 fail", "\u2139 skipped"))]
        lines.append(f"[注入不存在的选择器] exit={proc.returncode}")
        lines.append("红的用例：")
        lines.extend("  " + r for r in red)
        lines.append("诊断输出：")
        lines.extend("  " + d for d in diag_lines)
        lines.append("汇总：")
        lines.extend("  " + f for f in footer)
    finally:
        TARGET.write_bytes(original)

    after = sha256(TARGET)
    lines.append("")
    lines.append(f"复原后 sha256: {after}")
    lines.append(f"逐字节复原: {'OK' if after == before else 'MISMATCH'}")

    ok = (
        after == before
        and any("串口复测" in r for r in red)
        and sum(1 for d in diag_lines if d.startswith("[诊断]")) >= 3
    )
    lines.append("结论: " + ("[PASS] 诊断真的会打印（三段都在），红只落在被注入那一条"
                             if ok else "[FAIL] 诊断没打出来或红得不对"))

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
