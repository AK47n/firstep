"""反证探针（工单 record-write-hardening/07）：迁移的守卫就是**既有用例**——撤掉修，它们必须红。

三段（每段一类机制，逐条声明必须红 + 与实得 FAILED 对账 + 复原 sha256 逐字节）：

- **A 撤掉临界区**：`update_hwcheck_record` 里 `with path_lock(path):` → `if True:`
  （域层"读-改-写不丢字段"与端点级"两处入口串行"两条必须红）
- **B 撤掉共享原语的唯一临时名**：`atomic_io.atomic_write_text` 的临时名 → 固定名
  （"并发写不抢同一个临时名"那条必须红）
- **C 撤掉共享原语的清残渣**：`finally` 块 → `pass`（"写失败不留残渣"那条必须红）

三段都撤在**迁移后的落点**上：判据（既有用例）一行没改，只有并发那条用例的注入点
跟着写实现从 `hwcheck_triage.os` 搬到了 `atomic_io.os`。

形状照 `.scratch/record-write-hardening/probe-01-red.py`：**逐条声明**哪些用例必须红，
再把实得 `FAILED` 集合与声明对账——多出来的红如实打印，**不据此判 PASS**；
每段跑完复原源码并核对 sha256 逐字节相同（**字节往返**，不用文本模式）。

用法：`python .scratch/record-write-hardening/probe-07-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ATOMIC_IO = ROOT / "src" / "contest_generator" / "atomic_io.py"
TRIAGE = ROOT / "src" / "contest_generator" / "hwcheck_triage.py"
CASES = ["tests/test_hwcheck_triage.py", "tests/test_hwcheck.py"]
DOMAIN = "tests/test_hwcheck_triage.py::"
ENDPOINT = "tests/test_hwcheck.py::"

LOCK_BLOCK = [
    "    path = output_dir / HWCHECK_RECORD_FILENAME",
    "    with path_lock(path):",
    "        record = merge(read_hwcheck_record(output_dir))",
]
NO_LOCK_BLOCK = [
    "    path = output_dir / HWCHECK_RECORD_FILENAME",
    "    if True:",
    "        record = merge(read_hwcheck_record(output_dir))",
]
UNIQUE_TMP = '    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}")'
FIXED_TMP = '    tmp = path.with_name(f"{path.name}.tmp")'
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

NO_LOST_FIELD = DOMAIN + "test_update_hwcheck_record_does_not_lose_a_concurrent_field_write"
ENDPOINTS_SERIALISE = ENDPOINT + "test_two_endpoints_serialise_their_record_writes"
NO_SHARED_TMP = DOMAIN + "test_concurrent_record_writes_share_no_tmp_file"
NO_RESIDUE = DOMAIN + "test_record_write_failure_leaves_no_tmp_residue"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def run_tests() -> tuple[set[str], str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *CASES, "-q", "--tb=no", "-rf"],
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
    # 控制台 GBK 会把中文输出编成 GBK 字节，读数的 UTF-8 解码就成乱码（01 踩到过一次）
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    targets = (ATOMIC_IO, TRIAGE)
    sources = {path: path.read_bytes() for path in targets}
    texts = {path: raw.decode("utf-8") for path, raw in sources.items()}
    newlines = {path: newline_of(text) for path, text in texts.items()}

    def block(items: list[str], path: pathlib.Path) -> str:
        return newlines[path].join(items) + newlines[path]

    drop_lock = (TRIAGE, block(LOCK_BLOCK, TRIAGE), block(NO_LOCK_BLOCK, TRIAGE))
    fixed_name = (ATOMIC_IO, UNIQUE_TMP, FIXED_TMP)
    drop_cleanup = (
        ATOMIC_IO,
        block(CLEANUP_LINES, ATOMIC_IO),
        block(NO_CLEANUP_LINES, ATOMIC_IO),
    )
    segments = [
        ("A 撤掉临界区", [drop_lock], {NO_LOST_FIELD, ENDPOINTS_SERIALISE}),
        ("B 撤掉唯一临时名（固定名）", [fixed_name], {NO_SHARED_TMP}),
        ("C 撤掉清残渣", [drop_cleanup], {NO_RESIDUE}),
    ]

    for path in targets:
        print(
            f"# 被撤的源码：{path.relative_to(ROOT).as_posix()} "
            f"sha256={sha256(path)} 行尾={'CRLF' if newlines[path] == chr(13) + chr(10) else 'LF'}"
        )
    for case in CASES:
        print(f"# 判据文件（既有用例，一行未改）：{case} sha256={sha256(ROOT / case)}")
    print()

    verdicts: list[bool] = []
    for name, operations, declared in segments:
        print(f"== {name} ==")
        patched = dict(texts)
        missing_anchor = [
            (path.relative_to(ROOT).as_posix(), old)
            for path, old, _ in operations
            if old not in patched[path]
        ]
        if missing_anchor:
            print(f"   [!] 锚点失效（源码里找不到要撤的那段）：{missing_anchor!r}——探针该修了\n")
            verdicts.append(False)
            continue
        for path, old, new in operations:
            patched[path] = patched[path].replace(old, new, 1)
        try:
            for path in targets:
                path.write_bytes(patched[path].encode("utf-8"))
            failed, tail = run_tests()
        finally:
            for path in targets:
                path.write_bytes(sources[path])

        restored = all(
            sha256(path) == hashlib.sha256(sources[path]).hexdigest() for path in targets
        )
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

    print("== 复原后必须回绿（既有用例一行未改） ==")
    green_failed, green_tail = run_tests()
    print(f"   实得 FAILED：{sorted(green_failed) if green_failed else '（无）'}")
    print(f"   pytest 尾行：{green_tail}")
    print()

    ok = all(verdicts) and not green_failed
    print("结论：" + ("PASS（三段反证全成立）" if ok else "不成立，见上"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
