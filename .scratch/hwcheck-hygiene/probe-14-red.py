#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/14 的**反证探针**：`**粗**` 的渲染到底有没有人看着。

14 号单在渲染层把库数据里成对的 `**…**` 转成 `<strong>`。这条链路有三段，任何一段退回去
学生就又会看到字面星号——本探针一段一段撤，看那条浏览器判据红不红：

    ① 配方说明那一行退回 `esc()`
       → 「库数据里的说明文字零字面星号」必须红（配方 note 2434 处走的就是这条路）
    ② 说明弹窗的「备注」行退回 `escHtml()`
       → 同一条用例必须红（manifest 的 platforms.*.notes 1844 处走这条路）
    ③ 帮助函数本身退回"只转义不转换"
       → 同一条用例必须红（证明这一层不是"渲染点各写一遍"堆出来的）

每段：前置绿（跑**同一条**用例）→ 注入 → 必须红且红在那句断言上 → 复原 → sha256 逐字节相同。
跑法 = `--test-name-pattern` 只跑那一条（真浏览器夹具照起，一段约 10 秒）。

读数：`.scratch/hwcheck-hygiene/probe-14-red.txt`（经 readings.py 落盘）。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CORE = "src/contest_generator/static/js/fx/core.js"
PLAN = "src/contest_generator/static/js/fx/hwcheck-plan.js"
MODULE = "src/contest_generator/static/js/fx/module.js"
SPEC = "tests/browser/hwcheck.spec.mjs"
CASE = "库数据里的说明文字零字面星号"

SEGMENTS = [
    ("① 配方说明那一行退回 esc()",
     PLAN,
     '▸ ${escRich(line)}',
     '▸ ${esc(line)}',
     "配方说明里的字面星号没转掉"),
    ("② 说明弹窗的备注行退回 escHtml()",
     MODULE,
     "'<div class=\"mi-note\">备注：' + escRich(e.notes) + \"</div>\"",
     "'<div class=\"mi-note\">备注：' + escHtml(e.notes) + \"</div>\"",
     "说明弹窗里的字面星号没转掉"),
    ("③ 帮助函数退回「只转义不转换」",
     CORE,
     '  return esc(text)\n    .replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>")\n'
     '    .replace(/\\*\\*/g, "");',
     "  return esc(text);",
     "配方说明里的字面星号没转掉"),
]


def newline_of(raw: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in raw else b"\n"


def encode(anchor: str, raw: bytes) -> bytes:
    return anchor.replace("\n", "\r\n" if newline_of(raw) == b"\r\n" else "\n").encode("utf-8")


def run() -> tuple[int, str]:
    cmd = ["node", "--test", "--test-concurrency=1", f"--test-name-pattern={CASE}", SPEC]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    body = re.sub(r"\x1b\[[0-9;]*m", "", (proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode, body


def failure_block(out: str) -> str:
    at = out.find("failing tests:")
    return out[at:] if at >= 0 else out


def check_clean() -> None:
    for tag, rel, anchor, _repl, _expect in SEGMENTS:
        raw = (REPO / rel).read_bytes()
        count = raw.count(encode(anchor, raw))
        assert count == 1, (
            f"前置不干净：{rel}（换行 {newline_of(raw)!r}）里第 {tag} 段的锚点出现 {count} 次 —— "
            "上一次探针是不是被强杀了？先 `git checkout -- <那个文件>` 再跑")


def probe(tag: str, rel: str, anchor_text: str, repl: str, expect: str) -> tuple[bool, str]:
    path = REPO / rel
    before = path.read_bytes()
    digest = hashlib.sha256(before).hexdigest()[:16]
    anchor = encode(anchor_text, before)
    repl_b = encode(repl, before)
    assert before.count(anchor) == 1, f"{tag}：锚点在 {rel} 里出现 {before.count(anchor)} 次"

    path.write_bytes(before.replace(anchor, repl_b))
    assert path.read_bytes() != before, f"{tag}：注入没落上（{rel} 逐字节没变）"
    code, out = run()
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
    ap = argparse.ArgumentParser(description="14：库数据粗体渲染的反证")
    ap.add_argument("--only", default=None, help="只跑名字里含这个串的那一段")
    args = ap.parse_args()

    check_clean()
    results = []
    for tag, rel, anchor, repl, expect in SEGMENTS:
        if args.only and args.only not in tag:
            continue
        code, out = run()
        print(f"前置（{tag} 的用例，未注入）：退出码 {code} —— {'绿' if code == 0 else '红，前置不干净'}")
        if code != 0:
            print(failure_block(out)[:800])
            return 1
        ok, detail = probe(tag, rel, anchor, repl, expect)
        results.append((tag, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {tag}（{rel}）")
        print(f"        {detail}")

    bad = [tag for tag, ok, _ in results if not ok]
    tail = "；不成立：" + "、".join(bad) if bad else "（每段都是「注入即红、复原逐字节相同」）"
    print(f"\n结论：{len(results) - len(bad)}/{len(results)} 段成立{tail}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
