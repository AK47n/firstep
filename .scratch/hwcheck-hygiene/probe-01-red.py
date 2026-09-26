"""probe-01-red.py — 工单 hwcheck-hygiene/01 的判据强度反证（只改一处、跑完逐字节复原）。

做什么：把 `ui/hwcheck.js` 那条**新 import**（`hwcheckErrorHTML`）撤掉，让正文回到
"靠 `Object.assign(window, …)` 全局桥侥幸解析"的旧形态，然后跑**前端门禁**——
`tests/js/window-bridge-guard.test.mjs`（判据 ⑧）必须红；复原后 sha256 逐字节相同、
门禁回绿。

纪律（照仓内反证探针先例）：
  · 目标文件在盘上是 **CRLF**（`core.autocrlf=true`）：一律按**字节**读写，不用文本模式，
    免得换行归一把"复原复核"搞成假红；
  · 注入前先做**前置干净性检查**（锚点必须唯一命中），否则当场退出、不动文件；
  · 读数**先落盘再打印**（本机控制台是 GBK，`print` 抛 UnicodeEncodeError 会让整份证据丢）。

用法：`python .scratch/hwcheck-hygiene/probe-01-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TARGET = REPO / "src/contest_generator/static/js/ui/hwcheck.js"
OUT = pathlib.Path(__file__).resolve().parent / "probe-01-red.txt"

# 注入锚点：修复后的 import 行（CRLF 文件里这一行内部没有换行符，可按字节整段比对）
NEW_FORM = b"  hwcheckGenerateErrorHTML, hwcheckErrorHTML, hwcheckEmptyHTML, hwcheckPanelHTML,"
OLD_FORM = b"  hwcheckGenerateErrorHTML, hwcheckEmptyHTML, hwcheckPanelHTML,"
GATE = ["node", "--test", "tests/js/*.test.mjs"]

ANSI = re.compile(r"\x1b\[[0-9;]*m")
lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(GATE, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, ANSI.sub("", (proc.stdout or "") + (proc.stderr or ""))


def tail_counts(out: str) -> str:
    """抓 `node --test` 摘要行（它在 stderr 且带 ANSI，已在 run_gate 里剥掉）。"""
    keep = [ln.strip() for ln in out.splitlines()
            if ln.startswith(("ℹ tests", "ℹ pass", "ℹ fail", "ℹ skipped"))]
    return " / ".join(keep) if keep else "（没读到摘要行）"


def main() -> int:
    original = TARGET.read_bytes()
    before = sha256(original)
    say(f"目标：{TARGET.relative_to(REPO).as_posix()}")
    say(f"前置 sha256：{before}")

    # ---- 前置干净性检查：锚点必须唯一命中（否则不动文件） ----
    hits = original.count(NEW_FORM)
    if hits != 1:
        say(f"✗ 前置检查不通过：新形态锚点命中 {hits} 次（应为 1）——文件不在预期状态，未改动任何字节")
        write_and_print(1)
        return 1
    if OLD_FORM in original:
        say("✗ 前置检查不通过：旧形态仍在文件里（修复没落地？）——未改动任何字节")
        write_and_print(1)
        return 1
    say("前置检查：新形态锚点唯一命中 ✓ / 旧形态零命中 ✓")

    # ---- 注入：撤掉那条 import（= 回到靠全局桥解析的旧形态） ----
    try:
        TARGET.write_bytes(original.replace(NEW_FORM, OLD_FORM, 1))
        say(f"注入后 sha256：{sha256(TARGET.read_bytes())}（应不等于前置值）")

        code, out = run_gate()
        say("")
        say("--- 注入态：前端门禁 ---")
        say(tail_counts(out))
        say(f"退出码：{code}")
        red_ok = code != 0 and "window-bridge-guard" in out and "hwcheckErrorHTML" in out
        say(f"判据 ⑧ 报红：{'✓' if red_ok else '✗'}（要求：非零退出 + 点名 window-bridge-guard + 点名 hwcheckErrorHTML）")
        if red_ok:
            for ln in out.splitlines():
                if "hwcheckErrorHTML" in ln or "window-bridge-guard" in ln:
                    say("  " + ln.strip())
    finally:
        TARGET.write_bytes(original)          # 逐字节复原（异常路径也复原）

    after = sha256(TARGET.read_bytes())
    say("")
    say(f"复原后 sha256：{after}")
    say(f"逐字节相同：{'✓' if after == before else '✗'}")

    code2, out2 = run_gate()
    say("")
    say("--- 复原态：前端门禁 ---")
    say(tail_counts(out2))
    say(f"退出码：{code2}")
    say(f"复原后回绿：{'✓' if code2 == 0 else '✗'}")

    ok = red_ok and after == before and code2 == 0
    say("")
    say("结论：" + ("PASS —— 判据 ⑧ 有强度，且探针未留下任何改动" if ok else "FAIL"))
    write_and_print(0 if ok else 1)
    return 0 if ok else 1


def write_and_print(code: int) -> None:
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    print(f"\n读数已落盘：{OUT.relative_to(REPO).as_posix()}")


if __name__ == "__main__":
    sys.exit(main())
