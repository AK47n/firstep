#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/11 的**反证探针**：四件拆开之后，守卫真的还看得见吗。

拆分把"一个 1401 行的文件"变成"四个互相 import 的文件"，随之长出三类新的坏法——
它们都不报错、页面也照样能跑（真浏览器用例照样绿），只有结构守卫看得出来：

    ① **跨件反向依赖**（票面点名的那一段）：核心件 import 动作件 → `ui-cycle` 必须报环。
       反向边一旦被容忍，"谁都调得到"的那种大文件就会以另一种形状长回来。
    ② **名字搬丢**（改名 / 漏搬一个分支）：入口还 import 着旧名字 → `static-import-guard`
       判据③（全图 import↔export 逐名对账）必须点名"没有导出这个名字"——浏览器会抛
       SyntaxError，整页不初始化。
    ③ **用了没 import**（跨件调用少一条边）：`window-bridge-guard` 判据 ⑧ 必须点名。
       这一段的现实意义与 10 号单①同款：**桥兜住了运行态**，所以"页面还能跑"骗得过
       真浏览器验证，只有这条判据看得出来"它靠的是桥，不是 import"。

每段：前置绿 → 注入 → 判据必须红且点名 → 复原 → sha256 与前置逐字节相同。

判据强度纪律（本批先例，09/10 的探针同款）：
  · 探针**不许与任何读数并行**（注入期间磁盘上是坏形态）；
  · 启动先查"前置干净性"（三段锚点都在），强杀留下的注入态当场喊；
  · 逐字节读写；锚点按 `\\n` 写、由 `encode()` 按**文件实际换行**换算（工作树 CRLF/LF 混装）。

读数：`.scratch/hwcheck-hygiene/probe-11-red.txt`（经 readings.py 落盘）。
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CORE = "src/contest_generator/static/js/ui/hwcheck-core.js"
ENTRY = "src/contest_generator/static/js/ui/hwcheck.js"
ACTIONS = "src/contest_generator/static/js/ui/hwcheck-actions.js"

# (段名, 文件, 判据命令, 注入锚点（\n 写，落盘时换算）, 替换成, 期望点名的名字)
SEGMENTS = [
    ("① 跨件反向依赖（核心 → 动作）制造 ui 环",
     CORE,
     ["node", "--test", "tests/js/ui-cycle.test.mjs"],
     'import { $, state } from "/js/app.js";\n',
     'import { $, state } from "/js/app.js";\n'
     'import { generateHwcheck } from "/js/ui/hwcheck-actions.js";\n',
     "hwcheck-core.js"),
    ("② 名字搬丢（动作件里那段分支改了名，入口的接线还指着旧名）",
     ACTIONS,
     ["node", "--test", "tests/js/static-import-guard.test.mjs"],
     "export async function pickHwcheckParent(parentInput) {",
     "export async function probeRenamedPick(parentInput) {",
     "pickHwcheckParent"),
    ("③ 用了没 import（核心件少一条 fx 的 import 边）",
     CORE,
     ["node", "--test", "tests/js/window-bridge-guard.test.mjs"],
     "  hwcheckPlatformCardsHTML,\n",
     "",
     "hwcheckPlatformCardsHTML"),
]


def newline_of(raw: bytes) -> bytes:
    """文件的实际换行（CRLF 优先——混装文件里只要有一处 CRLF 就按 CRLF 编锚点）。"""
    return b"\r\n" if b"\r\n" in raw else b"\n"


def encode(anchor: str, raw: bytes) -> bytes:
    """把按 `\\n` 写的锚点换算成该文件的换行形态。"""
    return anchor.replace("\n", "\r\n" if newline_of(raw) == b"\r\n" else "\n").encode("utf-8")


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def failure_block(out: str) -> str:
    at = out.find("failing tests:")
    return out[at:] if at >= 0 else out


def check_clean() -> None:
    for tag, rel, _cmd, anchor, _repl, _name in SEGMENTS:
        raw = (REPO / rel).read_bytes()
        assert raw.count(encode(anchor, raw)) == 1, (
            f"前置不干净：{rel}（换行 {newline_of(raw)!r}）里第 {tag} 段的锚点不是恰好一处 —— "
            "上一次探针是不是被强杀了？先 `git checkout -- <那个文件>` 再跑")


def probe(tag: str, rel: str, cmd: list[str], anchor_text: str, repl: str,
          expect: str) -> tuple[bool, str]:
    path = REPO / rel
    before = path.read_bytes()
    digest = hashlib.sha256(before).hexdigest()[:16]
    anchor = encode(anchor_text, before)
    repl_b = encode(repl, before)
    assert before.count(anchor) == 1, f"{tag}：锚点在 {rel} 里出现 {before.count(anchor)} 次"

    path.write_bytes(before.replace(anchor, repl_b))
    assert path.read_bytes() != before, f"{tag}：注入没落上（{rel} 逐字节没变）"
    code, out = run(cmd)
    path.write_bytes(before)
    restored = hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    hits = [ln.strip() for ln in failure_block(out).split("\n") if expect in ln]
    ok = code != 0 and bool(hits) and restored == digest
    eol = "CRLF" if newline_of(before) == b"\r\n" else "LF"
    detail = (f"注入态退出码 {code}（文件换行 {eol}）"
              f"{'，点名了「' + hits[0][:70] + '」' if hits else '，**没有点到 ' + expect + '**'}；"
              f"复原 sha256 {restored}{'（与前置相同）' if restored == digest else '**不同！**'}")
    return ok, detail


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="11：四件拆开后的三类新坏法反证")
    ap.add_argument("--only", default=None, help="只跑名字里含这个串的那一段")
    args = ap.parse_args()

    check_clean()
    results = []
    for tag, rel, cmd, anchor, repl, expect in SEGMENTS:
        if args.only and args.only not in tag:
            continue
        code, out = run(cmd)
        print(f"前置（{tag} 的判据，未注入）：退出码 {code} —— "
              f"{'绿' if code == 0 else '红，前置不干净'}")
        if code != 0:
            print(failure_block(out)[:800])
            return 1
        ok, detail = probe(tag, rel, cmd, anchor, repl, expect)
        results.append((tag, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {tag}")
        print(f"        {detail}")

    bad = [tag for tag, ok, _ in results if not ok]
    tail = "；不成立：" + "、".join(bad) if bad else "（每段都是「注入即红、复原逐字节相同」）"
    print(f"\n结论：{len(results) - len(bad)}/{len(results)} 段成立{tail}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
