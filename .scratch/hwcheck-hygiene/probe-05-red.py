"""probe-05-red.py — 工单 hwcheck-hygiene/05 的判据强度反证（两处注入，各自跑完复原）。

* **A 上板清单那句又写死引脚** —— `hwcheck._heartbeat_led_hint` 换回硬编码字面量
  （= 评审 P2-11 的原缺陷）→ "改数据 → 文案跟着变"那条用例必须红。
* **B 白名单又从渲染文案里刮脚** —— 调用点把清单的 `check` 文本并进 `symptom` 那一处
  （= 旧的 `material_texts` 口径）→ "只在文案里出现过的脚不算事实"那条用例必须红。

每处按**字节**改写、跑完逐字节复原并复核 sha256；每条**逐条点名**声明哪些用例必须红，
并把实得 `FAILED` 集合与声明对账（多出来的红如实打印、不据此判 PASS）。
锚点按**文件实际换行形态**编码（本工作树是混的：`hwcheck_board.py` 是 CRLF、
`hwcheck_triage.py` / `hwcheck.py` 是 LF）。

用法：`python .scratch/hwcheck-hygiene/probe-05-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
HWCHECK = REPO / "src/contest_generator/hwcheck.py"
TRIAGE = REPO / "src/contest_generator/hwcheck_triage.py"
OUT = pathlib.Path(__file__).resolve().parent / "probe-05-red.txt"

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# ---- A：上板清单那句的渲染（数据 → 文案） ------------------------------------
A_NEW = '''    channels = led_builtin_pins(platform)
    if channels:
        pins = "/".join(channels)
        return f"板载三色 LED 在 {pins}（本程序用红灯通道 {_LED_CHANNEL}）；"
    first = led_first_pin(platform)
    if first:
        return f"板载用户 LED 是 {first}；"
    return ""'''
A_OLD = '''    return (
        "stm32 板载三色 LED 在 PC13/PC14/PC15（本程序用红灯通道 LED_RED），"
        "地猛星用户 LED 是 PA15；"
    )'''

# ---- B：白名单的引脚来源（数据 → 又变成渲染文案） ----------------------------
B_NEW = """            plan_texts=_plan_texts(
                section_rows, generic_rows, order, customs_rows
            ),"""
B_OLD = """            plan_texts=_plan_texts(
                section_rows, generic_rows, order, customs_rows
            ) + tuple(str(item.get("check", "")) for item in checklist_rows),"""

CASES = [
    ("A 上板清单那句又写死引脚", HWCHECK, A_NEW, A_OLD, [
        "tests/test_hwcheck.py::test_heartbeat_checklist_pins_come_from_the_selection_data",
    ]),
    ("B 白名单又从渲染文案里刮脚", TRIAGE, B_NEW, B_OLD, [
        "tests/test_hwcheck_triage.py::test_pin_that_only_appears_in_the_copy_is_not_a_fact",
    ]),
]

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_anchor(text: str, blob: bytes) -> bytes:
    """按目标文件在盘上的换行形态编码锚点（本工作树 LF / CRLF 混装）。"""
    newline = "\r\n" if blob.count(b"\r\n") else "\n"
    return text.replace("\n", newline).encode("utf-8")


def run_pytest(targets: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *targets],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    body = ANSI.sub("", (proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode, body.replace("\r\n", "\n").replace("\r", "\n")


def failed_tests(out: str) -> set[str]:
    found = set()
    for ln in out.splitlines():
        m = re.match(r"FAILED\s+(\S+)", ln.strip())
        if m:
            found.add(m.group(1).replace("\\", "/"))
    return found


def summary(out: str) -> str:
    for ln in reversed(out.splitlines()):
        if re.search(r"\d+ (passed|failed|error)", ln):
            return ln.strip()
    return "（没读到摘要行）"


def write_and_print(code: int) -> None:
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    print(f"\n读数已落盘：{OUT.relative_to(REPO).as_posix()}")


def main() -> int:
    payloads = {HWCHECK: HWCHECK.read_bytes(), TRIAGE: TRIAGE.read_bytes()}
    digests = {p: sha256(b) for p, b in payloads.items()}
    for path, digest in digests.items():
        say(f"目标：{path.relative_to(REPO).as_posix()}  前置 sha256：{digest}")
    for label, path, new_text, _old, _targets in CASES:
        if payloads[path].count(encode_anchor(new_text, payloads[path])) != 1:
            say(f"✗ 前置检查不通过：{label} 的新形态锚点不是唯一命中 —— 未改动任何字节")
            write_and_print(1)
            return 1
    say("前置检查：两处新形态锚点各唯一命中 ✓")

    all_ok = True
    for label, path, new_text, old_text, expected in CASES:
        say("")
        say(f"=== {label} ===")
        say(f"声明必须变红的用例（{len(expected)} 条）：")
        for node in expected:
            say(f"  · {node}")
        original = payloads[path]
        try:
            path.write_bytes(original.replace(encode_anchor(new_text, original),
                                              encode_anchor(old_text, original), 1))
            say(f"注入后 sha256：{sha256(path.read_bytes())}（应不等于前置值）")
            code, out = run_pytest(expected)
            failed = failed_tests(out)
            want = {n.replace("\\", "/") for n in expected}
            missing = sorted(want - failed)
            extra = sorted(failed - want)
            ok = code != 0 and not missing
            say(f"注入态读数：{summary(out)}  退出码：{code}")
            say(f"实得 FAILED（{len(failed)} 条）：")
            for node in sorted(failed):
                say(f"  · {node}")
            say("声明要红的逐条都红了 ✓" if not missing else f"✗ 声明要红却没红：{missing}")
            if extra:
                say(f"⚠ 另有未声明的红（本条不据此判 PASS，但记账）：{extra}")
        finally:
            path.write_bytes(original)
        after = sha256(path.read_bytes())
        say(f"复原 sha256：{after}  逐字节相同：{'✓' if after == digests[path] else '✗'}")
        code2, out2 = run_pytest(expected)
        say(f"复原态读数：{summary(out2)}  退出码：{code2}  回绿：{'✓' if code2 == 0 else '✗'}")
        all_ok = all_ok and ok and after == digests[path] and code2 == 0

    say("")
    say("结论：" + ("PASS —— 两处判据都有强度，且探针未留下任何改动" if all_ok else "FAIL"))
    write_and_print(0 if all_ok else 1)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
