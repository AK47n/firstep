"""probe-03-red.py — 工单 hwcheck-hygiene/03 的判据强度反证（两处注入，各自跑完复原）。

本单的正确性形状有两半，分别反证：

* **A 唯一临时名 + 异常不留残渣** —— 把 `write_hwcheck_record` 的临时名改回固定名
  （`HWCHECK_RECORD_FILENAME + ".tmp"`、`tmp.replace(path)`、去掉 finally）→
  `tests/test_hwcheck_triage.py` 里那两条（并发抢名 / 写失败留残渣）必须红。
* **B 读-改-写整段在临界区** —— 把 `update_hwcheck_record` 改成"无锁的读 → 合并 → 写"
  （函数还在、签名不变）→ 丢更新那两条（域层并发字段 / 端点在 LLM 窗口里的勾选）必须红。

两次注入都按**字节**改写、跑完逐字节复原并复核 sha256。

用法：`python .scratch/hwcheck-hygiene/probe-03-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TRIAGE = REPO / "src/contest_generator/hwcheck_triage.py"
OUT = pathlib.Path(__file__).resolve().parent / "probe-03-red.txt"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
lines: list[str] = []

# ---- A：临时名那一半 ----------------------------------------------------------
A_NEW = """    path = output_dir / HWCHECK_RECORD_FILENAME
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}")
    try:
        tmp.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    finally:
        # 异常路径不留残渣（`replace` 成功时 tmp 已经不在了；失败时它还在）
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:  # pragma: no cover —— 清不掉也不该把原异常盖掉
                pass
    return path"""
A_OLD = """    path = output_dir / HWCHECK_RECORD_FILENAME
    tmp = path.with_name(HWCHECK_RECORD_FILENAME + ".tmp")
    tmp.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path"""

# ---- B：临界区那一半 ----------------------------------------------------------
B_NEW = """    path = output_dir / HWCHECK_RECORD_FILENAME
    with _record_lock(path):
        record = merge(read_hwcheck_record(output_dir))
        write_hwcheck_record(output_dir, record)
        return record"""
B_OLD = """    record = merge(read_hwcheck_record(output_dir))
    write_hwcheck_record(output_dir, record)
    return record"""

CASES = [
    ("A 临时名改回固定名", A_NEW, A_OLD, [
        # `test_record_write_is_atomic_and_leaves_no_tmp` **不在**这张表里：它管的是
        # "成功路径不留残渣"，固定名实现在成功路径上也不留（临时文件被 rename 走了），
        # 所以它对这一处注入**没有区分力**——照实不声明，别拿它充数。
        "tests/test_hwcheck_triage.py::test_record_write_failure_leaves_no_tmp_residue",
        "tests/test_hwcheck_triage.py::test_concurrent_record_writes_share_no_tmp_file",
    ]),
    ("B 临界区撤掉（无锁读-改-写）", B_NEW, B_OLD, [
        "tests/test_hwcheck_triage.py::test_update_hwcheck_record_does_not_lose_a_concurrent_field_write",
        "tests/test_hwcheck.py::test_two_endpoints_serialise_their_record_writes",
    ]),
]

# 每个用例都要跑到的目标文件（`-k` 不带，整文件跑，免得漏掉别的红）
TARGET_FILES = sorted({t.split("::")[0] for _, _, _, ts in CASES for t in ts})


def say(text: str = "") -> None:
    lines.append(text)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_pytest(targets: list[str]) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "pytest", "-q", *targets]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    body = ANSI.sub("", (proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode, body.replace("\r\n", "\n").replace("\r", "\n")


def failed_tests(out: str) -> set[str]:
    """`FAILED <节点id>` 行 → 节点 id 集合（**逐条点名**，不看"有没有红"就下结论）。"""
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
    original = TRIAGE.read_bytes()
    before = sha256(original)
    say(f"目标：{TRIAGE.relative_to(REPO).as_posix()}")
    say(f"前置 sha256：{before}")
    for label, new_text, old_text, _ in CASES:
        if original.count(new_text.encode("utf-8")) != 1:
            say(f"✗ 前置检查不通过：{label} 的新形态锚点不是唯一命中 —— 未改动任何字节")
            write_and_print(1)
            return 1
    say("前置检查：两处新形态锚点各唯一命中 ✓")

    all_ok = True
    for label, new_text, old_text, expected in CASES:
        say("")
        say(f"=== {label} ===")
        say(f"声明必须变红的用例（{len(expected)} 条）：")
        for node in expected:
            say(f"  · {node}")
        try:
            TRIAGE.write_bytes(original.replace(new_text.encode("utf-8"),
                                                old_text.encode("utf-8"), 1))
            say(f"注入后 sha256：{sha256(TRIAGE.read_bytes())}（应不等于前置值）")
            # 整文件跑（不用 -k），跑出来的 FAILED 集合与本case声明的**逐条对账**
            code, out = run_pytest(TARGET_FILES)
            failed = failed_tests(out)
            want = {n.replace("\\", "/") for n in expected}
            missing = sorted(want - failed)
            extra = sorted(failed - want)
            ok = code != 0 and not missing
            say(f"注入态读数：{summary(out)}  退出码：{code}")
            say(f"实得 FAILED（{len(failed)} 条）：")
            for node in sorted(failed):
                say(f"  · {node}")
            if missing:
                say(f"✗ 声明要红却没红：{missing}")
            else:
                say("声明要红的逐条都红了 ✓")
            if extra:
                # 不判失败，但必须**如实打出来**（免得"红了一片"被当成声明那几条的证据）
                say(f"⚠ 另有未声明的红（本条不据此判 PASS，但记账）：{extra}")
        finally:
            TRIAGE.write_bytes(original)
        after = sha256(TRIAGE.read_bytes())
        say(f"复原 sha256：{after}  逐字节相同：{'✓' if after == before else '✗'}")
        code2, out2 = run_pytest(TARGET_FILES)
        say(f"复原态读数：{summary(out2)}  退出码：{code2}  回绿：{'✓' if code2 == 0 else '✗'}")
        all_ok = all_ok and ok and after == before and code2 == 0

    say("")
    say("结论：" + ("PASS —— 两半判据都有强度，且探针未留下任何改动" if all_ok else "FAIL"))
    write_and_print(0 if all_ok else 1)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
