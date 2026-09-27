#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/12 的**反证探针**：那几条"改写来的行为判据"真的看得见产品缺陷吗。

12 号单把 10 条读源码串的断言删掉、换成真浏览器用例。**证不了这一点，这次迁移就只是
把守卫换个地方闭眼**——"源码里有这行"那类断言撤掉产品代码也照样绿，本探针把产品行为
一处一处撤掉，看对应的浏览器用例红不红：

    ① 补 id 建议改回**整块重绘**（就地同步那一步撤掉）
       → 「逐字打字不被整块重绘吞掉」必须红（这一条替掉的就是当年那个真 bug）
    ② 初始化里少调一次 `renderHwcheckUnverifiedNote()`
       → 「顶部总口径真的在页面上」必须红
    ③ 删自建件时不再把它从**这次检测的选择**里摘掉
       → 「删掉一件时它同时从选择里去掉」必须红
    ④ 串口命令台的空态文案换回旧版（只说"库内配方"）
       → 「空态：串口复测那句把自建件也算进去」必须红

每段：前置绿（跑**同一条**用例）→ 注入 → 该用例必须红且红在那句断言上 → 复原 →
sha256 与前置逐字节相同。跑法 = `--test-name-pattern` 只跑那一条（真浏览器夹具照起，
一段十几秒；不这么跑就得每条都跑完 36 条 ≈ 2 分钟）。

判据强度纪律（本批先例，09/10/11 的探针同款）：
  · 探针**不许与任何读数并行**（注入期间磁盘上是坏形态）；
  · 启动先查"前置干净性"（四段锚点都在），强杀留下的注入态当场喊；
  · 逐字节读写；锚点按 `\\n` 写、由 `encode()` 按**文件实际换行**换算（工作树 CRLF/LF 混装）。

读数：`.scratch/hwcheck-hygiene/probe-12-red.txt`（经 readings.py 落盘）。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

UI = "src/contest_generator/static/js/ui/"
SPEC = "tests/browser/hwcheck.spec.mjs"

# (段名, 文件, 注入锚点（\n 写）, 替换成, 用例名（--test-name-pattern）, 期望红在哪句)
SEGMENTS = [
    ("① 输入回调改回整块重绘（就地同步那一步撤掉）",
     UI + "hwcheck-devices.js",
     '  if (e.target.closest("[data-my-device-field]")) syncMyDeviceForm();\n}\n\n'
     "// handleMyDeviceChange(e)",
     '  if (e.target.closest("[data-my-device-field]")) renderMyDevices();\n}\n\n'
     "// handleMyDeviceChange(e)",
     "逐字打字不被整块重绘吞掉",
     "打字被整块重绘吞掉了"),
    ("② 初始化里不再渲染顶部总口径",
     UI + "hwcheck.js",
     "  renderHwcheckUnverifiedNote();\n",
     "",
     "顶部总口径真的在页面上",
     "总口径没渲染出来"),
    ("③ 删自建件时不再从选择集里摘掉",
     UI + "hwcheck-devices.js",
     "    if ((hwcheckUI.devices || []).includes(id)) {\n"
     "      hwcheckUI.devices = hwcheckUI.devices.filter((slug) => slug !== id);\n"
     "      renderHwcheckDevices();\n"
     "      refreshHwcheckView();\n"
     "    }\n",
     "",
     "删掉一件时，它同时从这次检测的选择里去掉",
     "chips 里还挂着它"),
    ("④ 空态文案换回旧版（只提库内配方）",
     UI + "hwcheck-core.js",
     "    || '<div class=\"muted\">选好器件后点「预览检测程序」：这里会列出这一趟的串口'\n"
     "      + \"复测命令（库内器件按配方、自建件按它自己的探测小节），\"\n"
     "      + \"以及没有串口时为什么不能交互复测。</div>\");\n",
     "    || '<div class=\"muted\">选好器件后点「预览检测程序」：这里会列出这一趟的串口'\n"
     "      + \"复测命令（由库内配方决定），以及没有串口时为什么不能交互复测。</div>\");\n",
     "空态：串口复测那句把自建件也算进去",
     "空态文案没把自建件算进"),
]


def newline_of(raw: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in raw else b"\n"


def encode(anchor: str, raw: bytes) -> bytes:
    return anchor.replace("\n", "\r\n" if newline_of(raw) == b"\r\n" else "\n").encode("utf-8")


def run(pattern: str) -> tuple[int, str]:
    cmd = ["node", "--test", "--test-concurrency=1", f"--test-name-pattern={pattern}", SPEC]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    body = re.sub(r"\x1b\[[0-9;]*m", "", (proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode, body


def failure_block(out: str) -> str:
    at = out.find("failing tests:")
    return out[at:] if at >= 0 else out


def check_clean() -> None:
    for tag, rel, anchor, _repl, _pat, _expect in SEGMENTS:
        raw = (REPO / rel).read_bytes()
        count = raw.count(encode(anchor, raw))
        assert count == 1, (
            f"前置不干净：{rel}（换行 {newline_of(raw)!r}）里第 {tag} 段的锚点出现 {count} 次 —— "
            "上一次探针是不是被强杀了？先 `git checkout -- <那个文件>` 再跑")


def probe(tag: str, rel: str, anchor_text: str, repl: str, pattern: str,
          expect: str) -> tuple[bool, str]:
    path = REPO / rel
    before = path.read_bytes()
    digest = hashlib.sha256(before).hexdigest()[:16]
    anchor = encode(anchor_text, before)
    repl_b = encode(repl, before)
    assert before.count(anchor) == 1, f"{tag}：锚点在 {rel} 里出现 {before.count(anchor)} 次"

    path.write_bytes(before.replace(anchor, repl_b))
    assert path.read_bytes() != before, f"{tag}：注入没落上（{rel} 逐字节没变）"
    code, out = run(pattern)
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
    ap = argparse.ArgumentParser(description="12：改写来的行为判据的反证")
    ap.add_argument("--only", default=None, help="只跑名字里含这个串的那一段")
    args = ap.parse_args()

    check_clean()
    results = []
    for tag, rel, anchor, repl, pattern, expect in SEGMENTS:
        if args.only and args.only not in tag:
            continue
        code, out = run(pattern)
        print(f"前置（{tag} 的用例，未注入）：退出码 {code} —— {'绿' if code == 0 else '红，前置不干净'}")
        if code != 0:
            print(failure_block(out)[:800])
            return 1
        ok, detail = probe(tag, rel, anchor, repl, pattern, expect)
        results.append((tag, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {tag}（{rel}）")
        print(f"        {detail}")

    bad = [tag for tag, ok, _ in results if not ok]
    tail = "；不成立：" + "、".join(bad) if bad else "（每段都是「注入即红、复原逐字节相同」）"
    print(f"\n结论：{len(results) - len(bad)}/{len(results)} 段成立{tail}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
