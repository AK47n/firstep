#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/09 的**反证探针**：搬迁完整性自检到底有没有牙齿。

用法：

    python .scratch/hwcheck-hygiene/probe-09-red.py            # 跑全部四段（会改文件、每段自己复原）
    python .scratch/hwcheck-hygiene/probe-09-red.py --only ②   # 只跑一段

四段各自 = "注入旧形态 → 判据必须红 → 复原 → 逐字节相同"：

    ① 摘掉一个导出（`export function hwcheckAdviceHTML` → `function …`）
       → `hwcheck-split-integrity` 的 ① 必须点名它；
    ② 函数体里改一个字（`platform: target.id` → `platform: target.id + 1`）
       → ② 必须点名 `hwcheckSelectPlatform`；
    ③ 摘掉一条 window 桥条目（`hwcheckConsoleHTML,`）
       → ③ 必须点名它（**这一段的现实意义**：桥条目在搬迁里最容易悄悄掉一条，
         掉了以后页面内联脚本/探针取不到那个全局名，而所有"页面还能跑"的验证照样绿）；
    ④ 摘掉一条跨件 import（project 少 import `hwcheckDeviceSlugs`）
       → ④ 必须点名它（**这一段是 09 落盘时真发生过的**：判据 ⑧ 与这条一起抓的）。

判据强度纪律（本批先例）：
  · 段与段之间**不许并行**跑别的读数：探针期间磁盘上是被注入的形态；
  · 强杀会留下注入态 —— 启动先查一遍"前置干净性"（四段各自的锚点必须都在）；
  · 读写一律**逐字节**（`rb`/`wb`），别让文本模式换行归一制造整档重写；
  · 失败行按 `✖ 用例名` 解析（node 的 spec reporter 认这个，不认 pytest 的 FAILED）。

读数：`.scratch/hwcheck-hygiene/probe-09-red.txt`（经 readings.py 落盘）。
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FX = REPO / "src" / "contest_generator" / "static" / "js" / "fx"
TEST = "tests/js/hwcheck-split-integrity.test.mjs"

# (段名, 文件, 原文锚点, 替换成, 期望在失败报文里点名的名字)
SEGMENTS = [
    ("① 摘掉一个导出", "hwcheck-triage.js",
     b"export function hwcheckAdviceHTML(", b"function hwcheckAdviceHTML(",
     "hwcheckAdviceHTML"),
    ("② 函数体改一个字", "hwcheck-state.js",
     b"return { ...state, platform: target.id };",
     b"return { ...state, platform: target.id + 1 };",
     "hwcheckSelectPlatform"),
    ("③ 摘掉一条桥", "hwcheck-plan.js",
     b"hwcheckConsoleState, hwcheckConsoleHTML, hwcheckConsoleNoteHTML,",
     b"hwcheckConsoleState, hwcheckConsoleNoteHTML,",
     "hwcheckConsoleHTML"),
    ("④ 摘掉一条跨件 import", "hwcheck-project.js",
     b'import { hwcheckHintHTML, hwcheckDeviceSlugs } from "./hwcheck-state.js";',
     b'import { hwcheckHintHTML } from "./hwcheck-state.js";',
     "hwcheckDeviceSlugs"),
]


def run_test() -> tuple[int, str]:
    proc = subprocess.run(
        ["node", "--test", TEST], cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def failure_block(out: str) -> str:
    """node spec reporter 的**失败详情段**：用例名在 `✖` 行，断言正文（点名的名字）在
    `✖ failing tests:` 之后的缩进行里。名字要在**这一段**里找——07 踩过一次"判据确实红了、
    只是解析面写窄了"的假 FAIL，记账在 `probe-07-capture-c.txt`。"""
    at = out.find("failing tests:")
    return out[at:] if at >= 0 else out


def failure_lines(out: str) -> list[str]:
    return [ln.strip() for ln in out.split("\n") if ln.strip().startswith("✖")]


def check_clean() -> None:
    """前置干净性：四段的锚点都得在（强杀留下的注入态会让下面每一段都假红/假绿）。"""
    for tag, filename, anchor, _repl, _name in SEGMENTS:
        raw = (FX / filename).read_bytes()
        assert anchor in raw, (
            f"前置不干净：{filename} 里找不到第 {tag} 段的锚点 —— "
            "上一次探针是不是被强杀了？先 `git checkout -- src/contest_generator/static/js/fx/` 再跑")


def probe(tag: str, filename: str, anchor: bytes, repl: bytes, expect: str) -> tuple[bool, str]:
    path = FX / filename
    before = path.read_bytes()
    digest = hashlib.sha256(before).hexdigest()[:16]
    assert anchor in before, f"{tag}：锚点不在 {filename} 里"
    assert before.count(anchor) == 1, f"{tag}：锚点在 {filename} 里出现 {before.count(anchor)} 次"

    path.write_bytes(before.replace(anchor, repl))
    assert path.read_bytes() != before, f"{tag}：注入没落上（{filename} 逐字节没变）"
    code, out = run_test()
    path.write_bytes(before)
    restored = hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    lines = failure_lines(out)
    hits = [ln.strip() for ln in failure_block(out).split("\n") if expect in ln]
    ok_red = code != 0 and bool(hits)
    ok_restore = restored == digest
    detail = (f"注入态退出码 {code}；失败用例 {len(lines)} 条"
              f"{'，点名了「' + hits[0][:70] + '」' if hits else '，**没有点到 ' + expect + '**'}；"
              f"复原 sha256 {restored}{'（与前置相同）' if ok_restore else '**与前置不同！**'}")
    return (ok_red and ok_restore), detail


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="09：搬迁完整性自检的反证")
    ap.add_argument("--only", default=None, help="只跑名字里含这个串的那一段")
    args = ap.parse_args()

    check_clean()
    code, out = run_test()
    print(f"前置（未注入）：退出码 {code} —— {'绿，可以往下走' if code == 0 else '红，前置不干净，别往下跑'}")
    if code != 0:
        print("\n".join(failure_lines(out)))
        return 1

    results = []
    for tag, filename, anchor, repl, expect in SEGMENTS:
        if args.only and args.only not in tag:
            continue
        ok, detail = probe(tag, filename, anchor, repl, expect)
        results.append((tag, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {tag}（{filename}）")
        print(f"        {detail}")

    bad = [tag for tag, ok, _ in results if not ok]
    tail = "；不成立：" + "、".join(bad) if bad else "（每段都是「注入即红、复原逐字节相同」）"
    print(f"\n结论：{len(results) - len(bad)}/{len(results)} 段成立{tail}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
