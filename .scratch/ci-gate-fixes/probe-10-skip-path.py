#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe-10-skip-path.py — 工单 ci-gate-fixes/10 的**skip 路红证**。

问的问题：那条 `Debug/makefile` 断言在"本机没有 CCS"时**真的会 skip**、而不是继续红吗？
——本机装着 CCS（`find_ccs_tools` 探到 C:/ti/ccs2051 + ccs2050），所以只能**把探测口
临时堵掉**来造出 CI 的那一态。

做法：把 `compile_runner._CCS_SCAN_ROOT` 临时指到一个不存在的目录（"本机没装 CCS"的
等价状态），跑那一条用例：期望 **1 skipped / 0 failed**；再复原并复核 sha256。

纪律：会真改库内文件，**不许与测试套件同时跑**；逐字节读写 + sha256 复核复原；
读数先落盘再打印。
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "src" / "contest_generator" / "compile_runner.py"
DEFAULT_OUT = ROOT / ".scratch" / "ci-gate-fixes" / "probe-10-skip-path.txt"
TEST = "tests/test_my_devices_endpoint.py::test_generate_on_mspm0_keeps_the_i2c_instance_alive"

GOOD = '_CCS_SCAN_ROOT = "C:/ti"'
BAD = '_CCS_SCAN_ROOT = "C:/__no_ccs_for_probe__"'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> tuple[int, list[str]]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q", "-p", "no:cacheprovider", "-rs"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = proc.stdout + proc.stderr
    keep = [ln.strip() for ln in text.splitlines()
            if re.search(r"(SKIPPED|passed|failed|skipped|no CCS)", ln)]
    return proc.returncode, keep[-6:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)

    before = sha256(TARGET)
    original = TARGET.read_bytes()
    src = original.decode("utf-8")
    if BAD in src:
        print("[FAIL] 源文件停在上一轮的注入态，本探针拒绝跑。"
              "恢复：git checkout -- src/contest_generator/compile_runner.py")
        return 3
    if src.count(GOOD) != 1:
        print(f"[FAIL] 锚点不是恰好一处（{src.count(GOOD)}）——先人工看一眼。")
        return 2

    lines = [f"目标文件: {TARGET.relative_to(ROOT)}", f"注入前 sha256: {before}", ""]
    lines.append("[基线：本机有 CCS]")
    code_base, keep_base = run()
    lines.append(f"  exit={code_base}")
    lines.extend("  " + k for k in keep_base)

    try:
        TARGET.write_bytes(src.replace(GOOD, BAD, 1).encode("utf-8"))
        lines.append("")
        lines.append("[注入：把 CCS 扫描根指到不存在的目录 = 本机没装 CCS]")
        code_inj, keep_inj = run()
        lines.append(f"  exit={code_inj}")
        lines.extend("  " + k for k in keep_inj)
    finally:
        TARGET.write_bytes(original)

    after = sha256(TARGET)
    lines.append("")
    lines.append(f"复原后 sha256: {after}")
    lines.append(f"逐字节复原: {'OK' if after == before else 'MISMATCH'}")

    ok = (
        after == before
        and code_base == 0
        and code_inj == 0
        and any("skipped" in k and "1 skipped" in k for k in keep_inj)
    )
    lines.append("结论: " + (
        "[PASS] 没有 CCS 时该用例 skip（0 failed）、有 CCS 时真跑真断言"
        if ok else "[FAIL] skip 路没成立或复原不干净"))

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
