"""反证探针（工单 backlog-closeout/03）：逐段撤掉修 → 对应判据必须**点名红**。

三段（每段一类机制，逐条声明必须红 + 与实得 FAILED 对账 + 复原 sha256 逐字节）：

- **A 撤唯一临时名**（`atomic_io.atomic_write_via` 的临时名 → 固定名）：
  并发那条必须红（两个流式写者抢同一个临时文件）
- **B 撤清残渣**（`finally` 块 → `pass`）：两条"失败不留残渣"必须红
  （原语级 + 资料库解包级）
- **C 解包退回手搓固定临时名**（`materials_apply._extract_zip` 改回
  `.update-tmp` + `Path.replace`、无 `finally`）：解包失败那条红；
  **结构守卫也会红**（手搓站点回来了、例外清单里却没有它）——两条都如实声明

形状照 `.scratch/record-write-hardening/probe-01-red.py`：逐条声明 + 与实得 FAILED 对账 +
每段复原 sha256 逐字节相同（**字节往返**）。用法：
`python .scratch/backlog-closeout/probe-03-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ATOMIC_IO = ROOT / "src" / "contest_generator" / "atomic_io.py"
MATERIALS = ROOT / "src" / "contest_generator" / "materials_apply.py"
CASES = ["tests/test_atomic_io.py", "tests/test_materials_apply.py"]
ATOMIC = "tests/test_atomic_io.py::"
DOMAIN = "tests/test_materials_apply.py::"

CONCURRENT = ATOMIC + "test_concurrent_writes_share_no_tmp_file"
VIA_RESIDUE = ATOMIC + "test_atomic_write_via_failure_keeps_the_original_error_and_no_residue"
VIA_WRITE_RESIDUE = ATOMIC + "test_atomic_write_via_write_failure_cleans_the_partial_tmp"
APPLY_RESIDUE = DOMAIN + "test_apply_failure_leaves_no_update_tmp"
APPLY_WRITE_RESIDUE = DOMAIN + "test_apply_write_failure_cleans_the_partial_tmp"
APPLY_MANIFEST = DOMAIN + "test_apply_manifest_write_is_atomic"
GUARD = ATOMIC + "test_only_one_atomic_write_implementation_in_src"

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
EXTRACT_LINES = [
    "            with archive.open(member) as source:",
    "                atomic_write_via(target, partial(_copy_stream_to, source))",
]
EXTRACT_OLD = [
    '            tmp = target.with_name(target.name + ".update-tmp")',
    "            with archive.open(member) as source, open(tmp, \"wb\") as dest:",
    "                shutil.copyfileobj(source, dest)",
    "            tmp.replace(target)",
]


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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    targets = (ATOMIC_IO, MATERIALS)
    sources = {path: path.read_bytes() for path in targets}
    texts = {path: raw.decode("utf-8") for path, raw in sources.items()}
    newlines = {path: newline_of(text) for path, text in texts.items()}

    def block(items: list[str], path: pathlib.Path) -> str:
        return newlines[path].join(items) + newlines[path]

    fixed_name = (ATOMIC_IO, UNIQUE_TMP, FIXED_TMP)
    drop_cleanup = (ATOMIC_IO, block(CLEANUP_LINES, ATOMIC_IO), block(NO_CLEANUP_LINES, ATOMIC_IO))
    hand_rolled = (
        MATERIALS,
        block(EXTRACT_LINES, MATERIALS),
        block(EXTRACT_OLD, MATERIALS),
    )
    segments = [
        # 撤原语会**连带**老判据一起红（新旧入口共用同一份实现，这正是本单要的形状）——
        # 如实声明，别把它们当"多出来的红"。
        (
            "A 撤唯一临时名（固定名）",
            [fixed_name],
            {CONCURRENT, ATOMIC + "test_concurrent_writes_share_no_tmp_file"},
        ),
        (
            "B 撤清残渣（finally → pass）",
            [drop_cleanup],
            {
                VIA_RESIDUE,
                VIA_WRITE_RESIDUE,
                APPLY_RESIDUE,
                APPLY_WRITE_RESIDUE,
                APPLY_MANIFEST,
                ATOMIC + "test_atomic_write_text_replace_failure_leaves_no_residue",
                ATOMIC + "test_atomic_write_text_write_failure_leaves_no_residue",
            },
        ),
        ("C 解包退回手搓固定临时名", [hand_rolled], {APPLY_RESIDUE, APPLY_WRITE_RESIDUE, GUARD}),
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
            print(f"   [!] 锚点失效：{missing_anchor!r}——探针该修了\n")
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
            print(f"   [x] 多出来的红（如实打印，并据此判该段不成立）：{sorted(extra)}")
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
