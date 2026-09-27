"""反证探针（工单 record-write-hardening/05）：逐段撤掉修 → 对应判据必须**点名红**。

三段（每段一类机制，逐条声明必须红 + 与实得 FAILED 对账 + 复原 sha256 逐字节）：

- **A 撤掉"同一把锁"**：`master_store._write_meta` 与 `delete_master` 的 `path_lock` 都去掉
  （删除与写 meta 交错 → 留下"有 meta、没目录"的悬空母版：域层与端点两条判据必须红）
- **B 撤掉共享原语的清残渣**：`atomic_io.atomic_write_text` 的唯一临时名 → 固定名、
  `finally` 清残渣 → `pass`（"写失败留下 `.` 开头残渣"那条必须红）
- **C 撤回收走前的完整形状**：锁去掉 **＋** 唯一临时名 → 固定名（两个写者抢同一个
  `.stm32.json.tmp`；并发那条、删除交错那条、端点那条都必须红）

形状照 `.scratch/record-write-hardening/probe-01-red.py`：**逐条声明**哪些用例必须红，
再把实得 `FAILED` 集合与声明对账——多出来的红如实打印，**不据此判 PASS**；
每段跑完复原源码并核对 sha256 逐字节相同（**字节往返**，不用文本模式：Windows 上
文本写会把 `\n` 翻成 `\r\n`，复原的 sha 就对不上了）。

多行锚点按**文件实际行尾**拼：本工作树被 git 碰过之后可能是 CRLF，写死 `\n` 的锚点会静默失配。

用法：`python .scratch/record-write-hardening/probe-05-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ATOMIC_IO = ROOT / "src" / "contest_generator" / "atomic_io.py"
MASTER_STORE = ROOT / "src" / "contest_generator" / "master_store.py"
CASES = ["tests/test_master_store.py", "tests/test_webapp.py"]
DOMAIN = "tests/test_master_store.py::"
ENDPOINT = "tests/test_webapp.py::"

WRITE_META_LOCKED = [
    '    target = masters_dir / f"{meta.platform}.json"',
    "    with path_lock(target):",
    "        atomic_write_text(",
    "            target, json.dumps(meta.to_dict(), ensure_ascii=False, indent=2)",
    "        )",
]
WRITE_META_UNLOCKED = [
    '    target = masters_dir / f"{meta.platform}.json"',
    "    atomic_write_text(",
    "        target, json.dumps(meta.to_dict(), ensure_ascii=False, indent=2)",
    "    )",
]
DELETE_LOCKED = [
    '    meta_path = masters_dir / f"{platform}.json"',
    "    with path_lock(meta_path):",
    "        meta_path.unlink(missing_ok=True)",
]
DELETE_UNLOCKED = [
    '    meta_path = masters_dir / f"{platform}.json"',
    "    meta_path.unlink(missing_ok=True)",
]
UNIQUE_TMP = '    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}")'
# 收走前的形状是 `.{platform}.json.tmp`（**点开头**——`list_masters` 会跳过它，所以没人发现）；
# 撤的时候必须连这个点一起撤回来，否则残渣落在"非点开头"的名字上，判据反而抓不到
FIXED_TMP = '    tmp = path.with_name(f".{path.name}.tmp")'
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

CONCURRENT = DOMAIN + "test_concurrent_master_meta_writes_share_no_dot_temp"
INTERLEAVE = (
    DOMAIN + "test_delete_master_interleaved_with_a_meta_write_leaves_no_dangling_meta"
)
RESIDUE = (
    DOMAIN
    + "test_master_meta_write_failure_leaves_no_dot_temp_and_keeps_the_original_error"
)
ENDPOINT_DANGLING = (
    ENDPOINT + "test_masters_import_and_delete_do_not_leave_a_dangling_meta"
)


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
    targets = (ATOMIC_IO, MASTER_STORE)
    sources = {path: path.read_bytes() for path in targets}
    texts = {path: raw.decode("utf-8") for path, raw in sources.items()}
    newlines = {path: newline_of(text) for path, text in texts.items()}

    def block(items: list[str], path: pathlib.Path) -> str:
        return newlines[path].join(items) + newlines[path]

    # 每段 = (名字, [(目标文件, 旧片段, 新片段), …], 声明必须红的用例集合)
    drop_write_lock = (MASTER_STORE, block(WRITE_META_LOCKED, MASTER_STORE), block(WRITE_META_UNLOCKED, MASTER_STORE))
    drop_delete_lock = (MASTER_STORE, block(DELETE_LOCKED, MASTER_STORE), block(DELETE_UNLOCKED, MASTER_STORE))
    fixed_name = (ATOMIC_IO, UNIQUE_TMP, FIXED_TMP)
    drop_cleanup = (ATOMIC_IO, block(CLEANUP_LINES, ATOMIC_IO), block(NO_CLEANUP_LINES, ATOMIC_IO))
    segments = [
        (
            "A 撤掉「同一把锁」（写 meta 与删 meta 各自为政）",
            [drop_write_lock, drop_delete_lock],
            {INTERLEAVE, ENDPOINT_DANGLING},
        ),
        (
            "B 撤掉共享原语的清残渣（唯一临时名 → 固定名、finally → pass）",
            [fixed_name, drop_cleanup],
            {RESIDUE},
        ),
        (
            "C 撤回收走前的完整形状（锁 + 唯一临时名一起撤）",
            [drop_write_lock, drop_delete_lock, fixed_name],
            {CONCURRENT, INTERLEAVE, ENDPOINT_DANGLING},
        ),
    ]

    for path in targets:
        print(
            f"# 被撤的源码：{path.relative_to(ROOT).as_posix()} "
            f"sha256={sha256(path)} 行尾={'CRLF' if newlines[path] == chr(13) + chr(10) else 'LF'}"
        )
    for case in CASES:
        print(f"# 判据文件：{case} sha256={sha256(ROOT / case)}")
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

        restored = all(sha256(path) == hashlib.sha256(sources[path]).hexdigest() for path in targets)
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


if __name__ == "__main__":
    raise SystemExit(main())
