#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/10 的**反证探针**：消费者漏迁时，守卫真的会红吗。

`fx/hwcheck.js`（09 留的过渡态 barrel）删掉之后，"某个消费者还指着一件没迁过来的纯件"
是这一单最危险的坏法——它不会在类型层报错，只会**在运行时**炸（浏览器解析 / 调用时
`not defined`）。本探针把三种"漏迁"注入回去，看守卫抓不抓得到：

    ① 漏迁一整件（`ui/hwcheck.js` 指向 `hwcheck-plan.js` 的 import 整条删掉）
       → `window-bridge-guard` 判据 ⑧（模块正文的调用位不得靠 window 桥解析）必须点名
         plan 里的名字。**这一段的现实意义**：桥兜住了运行态，所以"页面还能跑"骗得过
         真浏览器验证，只有这条判据看得出来"它靠的是桥，不是 import"。
    ② 漏迁用例侧（`tests/js/hwcheck.test.mjs` 指向 `hwcheck-handoff.js` 的 import 整条删掉）
       → 前端门禁必须红，且报文里点名那个 `ReferenceError` 的名字。
    ③ 漏迁一整条边（把 `ui/hwcheck.js` 的 `hwcheck-state.js` import 改回**已删除的 barrel**）
       → `static-import-guard` 判据③（全图 import↔export 对账）必须报"文件不存在"——
         这正是票面点名的那条守卫，也是"某个消费者没迁完"最直接的形态
         （浏览器会抛 SyntaxError：请求的模块 404）。

每段：注入 → 判据必须红 → 复原 → sha256 与前置逐字节相同。

判据强度纪律（本批先例，09 的探针同款）：
  · 探针**不许与任何读数并行**（注入期间磁盘上是坏形态）；
  · 启动先查"前置干净性"（两段锚点都在），强杀留下的注入态当场喊；
  · 逐字节读写；失败行按 `✖ failing tests:` 段解析（07 的教训：解析面写窄会假 FAIL）。

读数：`.scratch/hwcheck-hygiene/probe-10-red.txt`（经 readings.py 落盘）。
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# (段名, 文件, 注入命令, 注入锚点（**\n 写，落盘时按文件实际换行换算**）, 替换成, 期望点名的名字)
#
# ⚠ 锚点一律按 `\n` 写、由 `encode()` 换算：本工作树 **LF / CRLF 混装**——
# `ui/hwcheck.js` 是 **CRLF**（实测 1390 行对 1390 个 CRLF），`tests/js/*` 是 LF。
# 按 LF 写死锚点会在 CRLF 文件上静默不中（本批先例：probe-0{4,5,6} 都踩过，见
# docs/agents/local-environment.md §0 的第 ② 条）。
SEGMENTS = [
    ("① 漏迁一整件（ui → plan）",
     "src/contest_generator/static/js/ui/hwcheck.js",
     ["node", "--test", "tests/js/window-bridge-guard.test.mjs"],
     'import {\n  hwcheckSectionsState, hwcheckSectionsHTML, hwcheckUnspecializedHTML,\n'
     '  hwcheckSectionsEmptyHTML, hwcheckCustomState, hwcheckCustomPlanHTML,\n'
     '  hwcheckCustomWiringHTML, hwcheckConsoleState, hwcheckConsoleHTML,\n'
     '  hwcheckConsoleNoteHTML,\n'
     '} from "/js/fx/hwcheck-plan.js";\n',
     "",
     "hwcheckSectionsState"),
    ("② 漏迁用例侧（test → handoff）",
     "tests/js/hwcheck.test.mjs",
     ["node", "--test", "tests/js/hwcheck.test.mjs"],
     'import {\n  hwcheckHandoffPlan, hwcheckHandoffHTML, hwcheckHandoffMerge,\n'
     '  hwcheckHandoffPinNote, hwcheckHandoffResultText,\n'
     '} from "../../src/contest_generator/static/js/fx/hwcheck-handoff.js";\n',
     "",
     "ReferenceError"),
    ("③ 漏迁一整条边（把 import 指回已删除的 barrel）",
     "src/contest_generator/static/js/ui/hwcheck.js",
     ["node", "--test", "tests/js/static-import-guard.test.mjs"],
     '} from "/js/fx/hwcheck-state.js";',
     '} from "/js/fx/hwcheck.js";',
     "文件不存在"),
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
        assert encode(anchor, raw) in raw, (
            f"前置不干净：{rel}（换行 {newline_of(raw)!r}）里找不到第 {tag} 段的锚点 —— "
            "上一次探针是不是被强杀了？先 `git checkout -- <那个文件>` 再跑")


def probe(tag: str, rel: str, cmd: list[str], anchor_text: str, repl: str,
          expect: str) -> tuple[bool, str]:
    path = REPO / rel
    before = path.read_bytes()
    digest = hashlib.sha256(before).hexdigest()[:16]
    anchor = encode(anchor_text, before)
    repl_b = encode(repl, before)
    assert anchor in before, f"{tag}：锚点不在 {rel} 里"
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
              f"{'，点名了「' + hits[0][:60] + '」' if hits else '，**没有点到 ' + expect + '**'}；"
              f"复原 sha256 {restored}{'（与前置相同）' if restored == digest else '**不同！**'}")
    return ok, detail


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="10：消费者漏迁的反证")
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
        print(f"[{'PASS' if ok else 'FAIL'}] {tag}（{rel}）")
        print(f"        {detail}")

    bad = [tag for tag, ok, _ in results if not ok]
    tail = "；不成立：" + "、".join(bad) if bad else "（每段都是「注入即红、复原逐字节相同」）"
    print(f"\n结论：{len(results) - len(bad)}/{len(results)} 段成立{tail}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
