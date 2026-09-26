"""probe-08-red-b2.py — 工单 hwcheck-hygiene/08 的**判据强度反证**（B2 那条）。

注入：把产品那一发登记的**重试**关掉（`index.html` 里的 `setTimeout(…, 300)` 改成空操作）
——这正是 `ci-gate-fixes/05` 修掉的那个形态。判据：`launcher-reload.spec.mjs` 的 B2
必须红（而且红在"重试没发生"那句，不是红在别处）。

⚠ 本单之前这条用例**本机 8 轮红 5 轮**却不是这个原因（是判据抢跑，已修）；
所以这次反证要看的是**注入后稳定红**、复原后**稳定绿**（两边各跑 3 轮）。

锚点按文件实际换行编码（`index.html` 在本检出是 CRLF——按 LF 写会静默不中）。
用法：python .scratch/hwcheck-hygiene/probe-08-red-b2.py
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from patch_bytes import encode_anchor, newline_of  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
INDEX = REPO / "src/contest_generator/static/index.html"
OUT = pathlib.Path(__file__).resolve().parent / "probe-08-red-b2.txt"
SPEC = "tests/browser/launcher-reload.spec.mjs"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
ROUNDS = 3

# 产品的重试（index.html 的登记 IIFE）
NEW = ("        .catch(function () {\n"
       "          if (left > 0) setTimeout(function () { attemptRegister(left - 1); }, 300);\n"
       "        });")
OLD = ("        .catch(function () {\n"
       "          if (left > 0) { /* 反证注入：重试关掉（ci-gate-fixes/05 之前的形态） */ }\n"
       "        });")

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def run_spec() -> tuple[int, str]:
    proc = subprocess.run(["node", "--test", "--test-concurrency=1", SPEC],
                          cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900)
    body = ANSI.sub("", (proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode, body.replace("\r\n", "\n").replace("\r", "\n")


def verdict(out: str) -> str:
    if "重试没发生" in out:
        return "红（重试没发生——正是要抓的那一句）"
    if re.search(r"ℹ fail 1", out):
        return "红（别的断言）"
    if re.search(r"ℹ fail 0", out):
        return "绿"
    return "（没读到摘要）"


def main() -> int:
    blob = INDEX.read_bytes()
    digest = sha(blob)
    say(f"目标：{INDEX.relative_to(REPO).as_posix()}  前置 sha256：{digest}  "
        f"换行：{'CRLF' if newline_of(blob) == chr(13) + chr(10) else 'LF'}")
    anchor = encode_anchor(NEW, blob)
    if blob.count(anchor) != 1:
        say(f"✗ 前置检查不通过：重试那段锚点命中 {blob.count(anchor)} 次（应为 1）"
            f"——未改动任何字节")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
        return 1
    say("前置检查：重试那段锚点唯一命中 ✓")

    ok = True
    for label, payload, expect_red in (
        ("注入态（重试关掉）", blob.replace(anchor, encode_anchor(OLD, blob), 1), True),
        ("复原态（逐字节还原）", blob, False),
    ):
        say("")
        say(f"=== {label}：连跑 {ROUNDS} 轮 {SPEC} ===")
        INDEX.write_bytes(payload)
        try:
            for index in range(1, ROUNDS + 1):
                code, out = run_spec()
                got = verdict(out)
                found_no_retry = "重试没发生" in out
                say(f"  第 {index} 轮：退出码 {code}  {got}")
                if expect_red and not (code != 0 and found_no_retry):
                    ok = False
                if not expect_red and code != 0:
                    ok = False
        finally:
            INDEX.write_bytes(blob)
        after = sha(INDEX.read_bytes())
        say(f"  复原 sha256：{after}  逐字节相同：{'✓' if after == digest else '✗'}")
        ok = ok and after == digest

    say("")
    say("结论：" + ("PASS —— 注入重试关掉时 B2 稳定红且红在点上，复原后稳定绿"
                    if ok else "FAIL"))
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    print(f"\n读数已落盘：{OUT.relative_to(REPO).as_posix()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
