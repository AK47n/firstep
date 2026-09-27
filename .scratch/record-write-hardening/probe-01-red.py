"""反证探针（工单 record-write-hardening/01）：把唯一临时名改回固定名 → 必须点名红。

形状照 `.scratch/hwcheck-hygiene/probe-03-red.py` 整改后的口径：
**逐条声明**哪些用例必须红，再把实得 `FAILED` 集合与声明对账——多出来的红如实打印，
**不据此判 PASS**；跑完复原源码并核对 sha256 逐字节相同。

用法：`python .scratch/record-write-hardening/probe-01-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGET = ROOT / "src" / "contest_generator" / "atomic_io.py"
UNIQUE_TMP = 'f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}"'
FIXED_TMP = 'f"{path.name}.tmp"'

# 声明：撤掉唯一临时名后，这一条必须红（其余用例与临时名无关，红了就是异常）
DECLARED = {"tests/test_atomic_io.py::test_concurrent_writes_share_no_tmp_file"}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tests() -> tuple[set[str], str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_atomic_io.py", "-q", "--tb=no", "-rf"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    failed = set(re.findall(r"^FAILED (\S+)", proc.stdout, flags=re.MULTILINE))
    return failed, proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""


def main() -> int:
    before = sha256(TARGET)
    # **字节往返**（不是 read_text/write_text）：Windows 上文本模式写会把 `\n` 翻成 `\r\n`，
    # 复原后的 sha256 就对不上了——"文本往返改文件"这个坑仓库里记过一次（backlog §19 顺带账）。
    raw = TARGET.read_bytes()
    source = raw.decode("utf-8")
    if UNIQUE_TMP not in source:
        print("[!] 找不到唯一临时名表达式——探针锚点失效，先修锚点")
        return 2

    print("== A 段：改回固定临时名 ==")
    try:
        TARGET.write_bytes(source.replace(UNIQUE_TMP, FIXED_TMP).encode("utf-8"))
        failed, tail = run_tests()
    finally:
        TARGET.write_bytes(raw)

    after = sha256(TARGET)
    print(f"   实得 FAILED：{sorted(failed) if failed else '（无）'}")
    print(f"   pytest 尾行：{tail}")
    print(f"   复原 sha256 一致：{before == after}")

    extra = failed - DECLARED
    missing = DECLARED - failed
    ok = not extra and not missing and before == after

    print("== B 段：复原后必须回绿 ==")
    green_failed, green_tail = run_tests()
    print(f"   实得 FAILED：{sorted(green_failed) if green_failed else '（无）'}")
    print(f"   pytest 尾行：{green_tail}")
    ok = ok and not green_failed

    print()
    if missing:
        print(f"[x] 声明必须红的用例没红：{sorted(missing)}")
    if extra:
        print(f"[x] 多出来的红（如实打印，不据此判 PASS）：{sorted(extra)}")
    if green_failed:
        print(f"[x] 复原后仍有红：{sorted(green_failed)}")
    print("结论：" + ("PASS（反证成立）" if ok else "不成立，见上"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
