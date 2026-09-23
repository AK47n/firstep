# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/10 的**收口驱动**：在**一份冻结的 revision** 上把本特性
全部「判据强度（反证）」探针依次重跑一遍，把读数汇总成一份证据文件。

为什么要有这一层（而不是只引用各单自己的读数）：

* 各单的探针读数取自各自的 revision；09 之后 `webapp.py` / `hwcheck_custom.py` 又动过，
  锚点可能失效——**探针的前置检查会大声失败**，但那要跑一遍才知道；
* 票面第 1 条要的是"每条新守卫各有一次停用后用例必须变红"，逐条散在十几个 .txt 里
  不好核，这里给一张总表（每条：探针名 / 退出码 / 末行读数 / 耗时）；
* 顺带核一遍**收尾指纹**：src/ + tests/ 下每个文件在整轮前后逐字节未变
  （探针自己会复原，这一层是"整轮下来也没留下痕迹"的独立判据）。

⚠ 纪律：**跑本驱动时别跑测试套件**（探针会真改源文件）。
⚠ 先落盘再打印（本机控制台 GBK）。

用法：`python .scratch/hwcheck-unknown-device/probe-10-guard-strength-all.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

# 强度探针（反证）：退出码 0 = 「反证成立」（每条注入都让对应用例变红 + 逐字节复原）
STRENGTH_PROBES = (
    "probe-01-c1-reverse.py",
    "probe-02-guard-strength.py",
    "probe-03-guard-strength.py",
    "probe-03b-sanitize-strength.py",
    "probe-04-guard-strength.py",
    "probe-05-guard-strength.py",
    "probe-05-guard-strength.mjs",
    "probe-06-guard-strength.py",
    "probe-06-guard-strength.mjs",
    "probe-07-guard-strength.py",
    "probe-07-guard-strength.mjs",
    "probe-08-guard-strength.py",
    "probe-08-guard-strength.mjs",
    "probe-09-guard-strength.py",
    "probe-11-guard-strength.py",
    "probe-12-guard-strength.py",
    "probe-12-guard-strength.mjs",
)

# 量具（不是反证）：退出码按各自的约定记，不进"反证成立"的合取
MEASUREMENTS = (
    # 工单 12：返回 1 = 守卫在（连字符 id 被三个端点全拒）
    ("probe-12-hyphen-id.py", 1),
    # 工单 11：赛题主线组合的重名读数（返回 0 = 与预期一致）
    ("probe-11-contest-dupname.py", 0),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_fingerprint() -> dict[str, str]:
    """src/ + tests/ 下每个文件的指纹（探针的落点都在这两棵子树里）。"""
    out: dict[str, str] = {}
    for root in (REPO / "src", REPO / "tests"):
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                out[str(path.relative_to(REPO)).replace("\\", "/")] = sha256(path)
    return out


def run(script: str) -> tuple[int, str, float]:
    """跑一支探针；返回（退出码, 末段读数, 耗时秒）。"""
    path = HERE / script
    cmd = (
        [sys.executable, str(path)]
        if script.endswith(".py")
        else ["node", str(path)]
    )
    started = time.time()
    proc = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=3600,
    )
    elapsed = time.time() - started
    lines = [
        line.strip() for line in (proc.stdout or "").splitlines() if line.strip()
    ]
    tail = " ｜ ".join(lines[-2:]) if lines else (proc.stderr or "").strip()[-200:]
    return proc.returncode, tail, elapsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", default=str(HERE / "probe-10-guard-strength-all.txt"),
        help="证据文件（UTF-8，先落盘再打印）",
    )
    args = parser.parse_args()

    lines: list[str] = []
    ok_all = True
    before = tree_fingerprint()
    lines.append(f"[1] 前置指纹：src/ + tests/ 共 {len(before)} 个文件")
    lines.append("")

    lines.append("[2] 强度探针（反证）——逐支重跑，退出码 0 = 反证成立")
    for script in STRENGTH_PROBES:
        code, tail, elapsed = run(script)
        verdict = "PASS（反证成立）" if code == 0 else f"FAIL（退出码 {code}）"
        lines.append(f"    {script:<36} {verdict}  ｜ {elapsed:6.1f}s ｜ {tail}")
        ok_all = ok_all and code == 0
    lines.append("")

    lines.append("[3] 量具（不是反证，退出码按各自约定）")
    for script, expected in MEASUREMENTS:
        code, tail, elapsed = run(script)
        verdict = "PASS（读数与预期一致）" if code == expected else (
            f"FAIL（预期 {expected}，实得 {code}）"
        )
        lines.append(f"    {script:<36} {verdict}  ｜ {elapsed:6.1f}s ｜ {tail}")
        ok_all = ok_all and code == expected
    lines.append("")

    after = tree_fingerprint()
    changed = sorted(
        key for key in set(before) | set(after) if before.get(key) != after.get(key)
    )
    lines.append(
        f"[4] 收尾指纹：{len(after)} 个文件"
        + ("逐字节未变 ✓" if not changed else f"有改动 ✗ → {changed[:10]}")
    )
    ok_all = ok_all and not changed
    lines.append("")
    lines.append(
        "=== 结论："
        + (
            f"收口成立（{len(STRENGTH_PROBES)} 支强度探针全 PASS + "
            f"{len(MEASUREMENTS)} 支量具读数一致 + 工作树逐字节未变）"
            if ok_all
            else "收口不成立（见上面读数）"
        )
        + " ==="
    )
    report = "\n".join(lines) + "\n"
    Path(args.out).write_text(report, encoding="utf-8")          # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
