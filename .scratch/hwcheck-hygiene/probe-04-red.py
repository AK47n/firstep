"""probe-04-red.py — 工单 hwcheck-hygiene/04 的判据强度反证（三处注入，各自跑完复原）。

本单有**三个**可独立打回原形的形状，逐个反证：

* **A 记录读失败的两支话术合回一处** —— `read_hwcheck_record` 回到
  `except (OSError, json.JSONDecodeError)` 共用"损坏…可以删掉重填"那一句 →
  域层那条用例必须红（读不出来被说成损坏、还引导删记录）。
* **B 母版配置的静默降级放回去** —— `read_master_syscfg` 的 `except OSError` 回到
  `return None` → "存在但读不出来"又变成"没有这份配置" → 域层与端点两条用例必须红。
* **C 容量跳过那句话撤掉** —— `PIN_CAPACITY_SKIPPED_NOTE` 置空 → 跳过容量判定又不吭声
  → 计划与载荷两条用例必须红。

每处都按**字节**改写、跑完逐字节复原并复核 sha256；每条都**逐条点名**声明哪些用例必须红，
并把实得 `FAILED` 集合与声明对账（多出来的红如实打印、不据此判 PASS）。

用法：`python .scratch/hwcheck-hygiene/probe-04-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BOARD = REPO / "src/contest_generator/hwcheck_board.py"
TRIAGE = REPO / "src/contest_generator/hwcheck_triage.py"
OUT = pathlib.Path(__file__).resolve().parent / "probe-04-red.txt"

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# ---- A：记录读失败的两支话术 ------------------------------------------------
A_NEW = '''    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HwCheckError(
            f"检测记录 {HWCHECK_RECORD_FILENAME} 读不出来：{exc} —— "
            "它可能正被别的程序占用（编辑器 / 同步盘），或当前账户没有读权限；"
            "先把占用它的程序关掉再试。"
        ) from exc
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise HwCheckError(
            f"检测记录 {HWCHECK_RECORD_FILENAME} 损坏（不是合法 JSON）：{exc} —— "
            "可以把它删掉重填，或修好 JSON 再看"
        ) from exc'''
A_OLD = '''    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HwCheckError(
            f"检测记录 {HWCHECK_RECORD_FILENAME} 损坏（不是合法 JSON）：{exc} —— "
            "可以把它删掉重填，或修好 JSON 再看"
        ) from exc'''

# ---- B：母版配置的静默降级 --------------------------------------------------
B_NEW = '''    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HwCheckError(
            f"母版配置 {path.name} 读不出来：{exc} —— "
            "它可能正被别的程序占用（编辑器 / 资源管理器预览），或当前账户没有读权限；"
            "先把占用它的程序关掉（或把母版换一处放置）再试。"
        ) from exc'''
B_OLD = '''    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None'''

# ---- C：容量跳过那句话 ------------------------------------------------------
C_NEW = '''PIN_CAPACITY_SKIPPED_NOTE = (
    "没导入 mspm0 母版（或母版里没有 mspm0.syscfg）：这一趟没判「装不装得下」"
    "——先到「母版库」把 mspm0 母版导入，再回来看这一步的结论。"
)'''
C_OLD = 'PIN_CAPACITY_SKIPPED_NOTE = ""'

CASES = [
    ("A 记录读失败的两支话术合回一处", TRIAGE, A_NEW, A_OLD, [
        "tests/test_hwcheck_triage.py::test_record_read_failure_is_not_reported_as_corruption",
    ]),
    ("B 母版配置的静默降级放回去", BOARD, B_NEW, B_OLD, [
        "tests/test_hwcheck_board.py::test_master_syscfg_missing_is_none_but_unreadable_is_loud",
        "tests/test_hwcheck_board.py::test_readback_still_opens_when_the_master_syscfg_is_locked",
        "tests/test_hwcheck.py::test_preview_400s_when_the_master_syscfg_cannot_be_read",
    ]),
    ("C 容量跳过那句话撤掉", BOARD, C_NEW, C_OLD, [
        "tests/test_hwcheck_board.py::test_missing_master_syscfg_skips_capacity_but_says_so",
        "tests/test_hwcheck_board.py::test_view_payload_discloses_the_skipped_capacity_check",
    ]),
]

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_anchor(text: str, blob: bytes) -> bytes:
    """把锚点按**目标文件在盘上的换行形态**编码（本工作树是混的：`hwcheck_board.py`
    是 CRLF、`hwcheck_triage.py` 是 LF——按 LF 写死锚点会在前者上"找不到"，而
    `local-environment.md` 第 2 节已把这条记成纪律）。
    """
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
    payloads = {TRIAGE: TRIAGE.read_bytes(), BOARD: BOARD.read_bytes()}
    digests = {p: sha256(b) for p, b in payloads.items()}
    for path, digest in digests.items():
        say(f"目标：{path.relative_to(REPO).as_posix()}  前置 sha256：{digest}")
    for label, path, new_text, _old, _targets in CASES:
        if payloads[path].count(encode_anchor(new_text, payloads[path])) != 1:
            say(f"✗ 前置检查不通过：{label} 的新形态锚点不是唯一命中 —— 未改动任何字节")
            write_and_print(1)
            return 1
    say("前置检查：三处新形态锚点各唯一命中 ✓")

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
    say("结论：" + ("PASS —— 三处判据都有强度，且探针未留下任何改动" if all_ok else "FAIL"))
    write_and_print(0 if all_ok else 1)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
