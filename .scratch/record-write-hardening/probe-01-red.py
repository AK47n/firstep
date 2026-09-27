"""反证探针（工单 record-write-hardening/01）：逐段撤掉修 → 对应判据必须**点名红**。

三段：
- **A 固定临时名**：`{path.name}.tmp-{pid}-{计数}` → `{path.name}.tmp`
- **B 撤掉清残渣**：`finally` 块整体去掉（只留 `pass`）
- **C 锁键不归一**：`normcase(abspath(path))` → `str(path)`

形状照 `.scratch/hwcheck-hygiene/probe-03-red.py` 整改后的口径：**逐条声明**哪些用例必须红，
再把实得 `FAILED` 集合与声明对账——多出来的红如实打印，**不据此判 PASS**；
每段跑完复原源码并核对 sha256 逐字节相同（**字节往返**，不用文本模式：Windows 上
文本写会把 `\n` 翻成 `\r\n`，复原的 sha 就对不上了）。

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
CASES = "tests/test_atomic_io.py"
PREFIX = "tests/test_atomic_io.py::"

UNIQUE_TMP = 'f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}"'
FIXED_TMP = 'f"{path.name}.tmp"'
CLEANUP_LINES = [
    "    finally:",
    "        # `replace` 成功时 tmp 已经不在了；失败时它还在，清掉它",
    "        if tmp.exists():",
    "            try:",
    "                tmp.unlink()",
    "            except OSError:  # pragma: no cover —— 清不掉也不该把原异常盖掉",
    "                pass",
]
NO_CLEANUP_LINES = ["    finally:", "        pass"]
LOCK_KEY = "key = os.path.normcase(os.path.abspath(path))"
RAW_KEY = "key = str(path)"


def _segment(
    name: str, old_lines: list[str], new_lines: list[str], declared: set[str], newline: str
) -> tuple[str, str, str, set[str]]:
    """多行锚点按**文件实际行尾**拼——工作树被 git 碰过之后可能是 CRLF，
    写死 `\\n` 的锚点会静默失配（本轮真踩到：A/C 单行锚点照常，B 多行锚点失效）。"""
    join = lambda lines: newline.join(lines) + newline  # noqa: E731
    return name, join(old_lines), join(new_lines), declared


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tests() -> tuple[set[str], str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", CASES, "-q", "--tb=no", "-rf"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    failed = set(re.findall(r"^FAILED (\S+)", out, flags=re.MULTILINE))
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return failed, tail


def main() -> int:
    # 控制台 GBK 会把中文输出编成 GBK 字节，读数的 UTF-8 解码就成乱码（本轮踩到过一次）
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = TARGET.read_bytes()
    source = raw.decode("utf-8")
    newline = "\r\n" if "\r\n" in source else "\n"
    segments: list[tuple[str, str, str, set[str]]] = [
        (
            "A 固定临时名",
            UNIQUE_TMP,
            FIXED_TMP,
            {PREFIX + "test_concurrent_writes_share_no_tmp_file"},
        ),
        _segment(
            "B 撤掉清残渣",
            CLEANUP_LINES,
            NO_CLEANUP_LINES,
            {
                PREFIX + "test_atomic_write_text_replace_failure_leaves_no_residue",
                PREFIX + "test_atomic_write_text_write_failure_leaves_no_residue",
            },
            newline,
        ),
        (
            "C 锁键不归一",
            LOCK_KEY,
            RAW_KEY,
            {PREFIX + "test_path_lock_is_shared_for_normalised_spellings_of_one_path"},
        ),
    ]
    print(f"# 被撤的源码：{TARGET.relative_to(ROOT).as_posix()} sha256={sha256(TARGET)}")
    print(f"# 判据文件：{CASES} sha256={sha256(ROOT / CASES)}")
    print(f"# 源码行尾：{'CRLF' if newline == chr(13) + chr(10) else 'LF'}")
    print()

    verdicts: list[bool] = []
    for name, old, new, declared in segments:
        print(f"== {name} ==")
        if old not in source:
            print("   [!] 锚点失效（源码里找不到要撤的那段）——探针该修了\n")
            verdicts.append(False)
            continue
        try:
            TARGET.write_bytes(source.replace(old, new, 1).encode("utf-8"))
            failed, tail = run_tests()
        finally:
            TARGET.write_bytes(raw)

        restored = sha256(TARGET) == sha256_bytes(raw)
        missing = declared - failed
        extra = failed - declared
        print(f"   声明必须红：{sorted(declared)}")
        print(f"   实得 FAILED：{sorted(failed) if failed else '（无）'}")
        print(f"   pytest 尾行：{tail}")
        print(f"   复原 sha256 逐字节相同：{restored}")
        if missing:
            print(f"   [x] 声明必须红的没红：{sorted(missing)}")
        if extra:
            print(f"   [x] 多出来的红（如实打印，不据此判 PASS）：{sorted(extra)}")
        verdicts.append(not missing and not extra and restored)
        print()

    print("== 复原后必须回绿 ==")
    green_failed, green_tail = run_tests()
    print(f"   实得 FAILED：{sorted(green_failed) if green_failed else '（无）'}")
    print(f"   pytest 尾行：{green_tail}")
    print()

    ok = all(verdicts) and not green_failed
    print("结论：" + ("PASS（三段反证全成立）" if ok else "不成立，见上"))
    return 0 if ok else 1


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
