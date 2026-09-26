"""loop-08-aftereach.py — 工单 hwcheck-hygiene/08 的**复现回路**：连跑浏览器 spec，
把每轮的 `[afterEach]` 告警与用时抓出来（诊断第一步，见 `diagnosing-bugs` 的 Phase 1）。

为什么不用整条浏览器门禁：那要 4 分钟/轮，而这 28 轮的观察窗只需要 `hwcheck.spec.mjs`
（13 条用例、共用一张页面，`afterEach` 就是它里面的）——**一次只改一个变量**，
先把回路做快再谈复现率。

用法：
    python .scratch/hwcheck-hygiene/loop-08-aftereach.py            # 默认 10 轮
    python .scratch/hwcheck-hygiene/loop-08-aftereach.py 20
输出：`.scratch/hwcheck-hygiene/loop-08-aftereach-<stamp>.txt`（每轮退出码 / 用时 /
告警原文 / 该轮往前的 40 行上下文——告警出现在哪一条用例之后，靠上下文认）。
"""

from __future__ import annotations

import datetime
import pathlib
import re
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = pathlib.Path(__file__).resolve().parent
SPEC = "tests/browser/hwcheck.spec.mjs"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
WARNING = "[afterEach]"


def main(argv: list[str]) -> int:
    rounds = int(argv[0]) if argv else 10
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = OUT_DIR / f"loop-08-aftereach-{stamp}.txt"
    lines: list[str] = [
        "# 复现回路：连跑 tests/browser/hwcheck.spec.mjs，看 [afterEach] 告警复现率",
        f"# 命令：node --test --test-concurrency=1 {SPEC}",
        f"# 轮数：{rounds}   开始：{datetime.datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    hits = 0
    for index in range(1, rounds + 1):
        started = time.monotonic()
        proc = subprocess.run(
            ["node", "--test", "--test-concurrency=1", SPEC],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=900)
        elapsed = time.monotonic() - started
        body = ANSI.sub("", (proc.stdout or "") + (proc.stderr or ""))
        body = body.replace("\r\n", "\n").replace("\r", "\n")
        warn = [ln for ln in body.splitlines() if WARNING in ln]
        if warn:
            hits += 1
        summary = next((ln.strip() for ln in reversed(body.splitlines())
                        if re.search(r"ℹ (pass|fail)", ln)), "（没读到摘要）")
        fails = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("✖")]
        lines.append(f"## 第 {index} 轮：退出码 {proc.returncode}  用时 {elapsed:.1f}s  "
                     f"{summary}  告警 {len(warn)} 条")
        for ln in fails:
            lines.append(f"   失败行：{ln[:160]}")
        for ln in warn:
            lines.append(f"   ⚠ {ln[:400]}")
            # 告警夹在哪些用例之间 = "哪一条用例之后清的"——留 6 行上下文
            where = body.splitlines().index(ln)
            for ctx in body.splitlines()[max(0, where - 6):where]:
                lines.append(f"      | {ctx[:150]}")
        lines.append("")
        print(f"第 {index}/{rounds} 轮：退出码 {proc.returncode}  {elapsed:.1f}s  "
              f"{summary}  告警 {len(warn)}")
    lines.append(f"=== 结论：{rounds} 轮里 {hits} 轮出现 [afterEach] 告警 "
                 f"（复现率 {hits}/{rounds}）===")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"\n读数已落盘：{out.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
