"""probe-02-red.py — 工单 hwcheck-hygiene/02 的判据强度反证（只改一处、跑完逐字节复原）。

做什么：把 `fx/hwcheck.js` 里**第 2 处**（`hwcheckChannelNoteHTML` 的「不用你自己改」）那句的
markdown 星号**塞回去**（`<strong>…</strong>` → `**…**`，即回到修复前的形态），然后跑**前端门禁**
——`tests/js/bold-marker-guard.test.mjs`（判据 ⑨）必须红；复原后 sha256 逐字节相同、门禁回绿。

为什么挑这一处：工单点明它是"双通道平台上**几乎必现**"的那条，也是**语义最不能糊**的一句
（学生判断"要不要自己改线"的依据）——它是这条判据最该抓住的一处。

纪律（照 `probe-01-red.py`）：按**字节**读写、前置干净性检查、读数先落盘再打印。

用法：`python .scratch/hwcheck-hygiene/probe-02-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TARGET = REPO / "src/contest_generator/static/js/fx/hwcheck.js"
OUT = pathlib.Path(__file__).resolve().parent / "probe-02-red.txt"

# 注入锚点：修复后的形态（一行之内，不含换行；CRLF/LF 检出都按字节比得中）
NEW_FORM = "<strong>不用你自己改</strong>".encode("utf-8")
OLD_FORM = "**不用你自己改**".encode("utf-8")
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
    body = ANSI.sub("", (proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode, body.replace("\r\n", "\n").replace("\r", "\n")


def counts(out: str) -> str:
    keep = [ln.strip() for ln in out.splitlines()
            if ln.strip().startswith(("ℹ tests", "ℹ pass", "ℹ fail"))]
    return " / ".join(keep) if keep else "（没读到摘要行）"


def write_and_print(code: int) -> None:
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    print(f"\n读数已落盘：{OUT.relative_to(REPO).as_posix()}")


def main() -> int:
    original = TARGET.read_bytes()
    before = sha256(original)
    say(f"目标：{TARGET.relative_to(REPO).as_posix()}")
    say(f"前置 sha256：{before}")

    hits = original.count(NEW_FORM)
    if hits != 1:
        say(f"✗ 前置检查不通过：新形态锚点命中 {hits} 次（应为 1）——文件不在预期状态，未改动任何字节")
        write_and_print(1)
        return 1
    if OLD_FORM in original:
        say("✗ 前置检查不通过：旧形态（字面星号）仍在文件里 —— 未改动任何字节")
        write_and_print(1)
        return 1
    say("前置检查：新形态锚点唯一命中 ✓ / 旧形态零命中 ✓")

    red_ok = False
    try:
        TARGET.write_bytes(original.replace(NEW_FORM, OLD_FORM, 1))
        say(f"注入后 sha256：{sha256(TARGET.read_bytes())}（应不等于前置值）")

        code, out = run_gate()
        say("")
        say("--- 注入态：前端门禁 ---")
        say(counts(out))
        say(f"退出码：{code}")
        red_ok = code != 0 and "bold-marker-guard" in out and "不用你自己改" in out
        say(f"判据 ⑨ 报红：{'✓' if red_ok else '✗'}"
            "（要求：非零退出 + 点名 bold-marker-guard + 点名「不用你自己改」）")
        if red_ok:
            for ln in out.splitlines():
                if "不用你自己改" in ln or "bold-marker-guard" in ln:
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
    say(counts(out2))
    say(f"退出码：{code2}")
    say(f"复原后回绿：{'✓' if code2 == 0 else '✗'}")

    ok = red_ok and after == before and code2 == 0
    say("")
    say("结论：" + ("PASS —— 判据 ⑨ 有强度，且探针未留下任何改动" if ok else "FAIL"))
    write_and_print(0 if ok else 1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
