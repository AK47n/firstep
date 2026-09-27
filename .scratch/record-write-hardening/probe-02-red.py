"""反证探针（工单 record-write-hardening/02）：逐段撤掉修 → 对应判据必须**点名红**。

三段：
- **A 撤掉临界区**：`drafts.update_drafts` 里 `with path_lock(path):` → `if True:`（读-改-写不再串行）
- **B 撤掉共享原语**：`atomic_io.atomic_write_text` 撤回收走前的形状——**唯一临时名 → 固定临时名**
  ＋ **`finally` 清残渣 → `pass`**（撤在**原语所在的模块**里：判据的注入点正是 `atomic_io.os`，
  撤在调用方 `drafts.py` 会让注入点压根不被走到 = 红得不是机制，双轴评审 2026-09-27 点名过）
- **C 端点退回旧形状**：两个端点改回 `read_drafts` → 纯函数 → `write_drafts`（绕开 `update_drafts`）

形状照 `.scratch/record-write-hardening/probe-01-red.py`：**逐条声明**哪些用例必须红，
再把实得 `FAILED` 集合与声明对账——多出来的红如实打印，**不据此判 PASS**；
每段跑完复原源码并核对 sha256 逐字节相同（**字节往返**，不用文本模式：Windows 上
文本写会把 `\n` 翻成 `\r\n`，复原的 sha 就对不上了）。

多行锚点按**文件实际行尾**拼：本工作树被 git 碰过之后可能是 CRLF，写死 `\n` 的锚点会静默失配。

用法：`python .scratch/record-write-hardening/probe-02-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ATOMIC_IO = ROOT / "src" / "contest_generator" / "atomic_io.py"
DRAFTS = ROOT / "src" / "contest_generator" / "drafts.py"
WEBAPP = ROOT / "src" / "contest_generator" / "webapp.py"
CASES = "tests/test_drafts.py"
PREFIX = "tests/test_drafts.py::"

LOCK_BLOCK = [
    "    path = output_dir / IDEA_DRAFTS_FILENAME",
    "    with path_lock(path):",
    "        drafts = merge(read_drafts(output_dir))",
    "        write_drafts(output_dir, drafts)",
    "        return drafts",
]
NO_LOCK_BLOCK = [
    "    path = output_dir / IDEA_DRAFTS_FILENAME",
    "    if True:",
    "        drafts = merge(read_drafts(output_dir))",
    "        write_drafts(output_dir, drafts)",
    "        return drafts",
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
ENDPOINT_IMPORT_OLD = "        from .drafts import add_draft, update_drafts"
ENDPOINT_IMPORT_NEW = "        from .drafts import add_draft, read_drafts, write_drafts"
ENDPOINT_ADD_OLD = (
    "        updated = update_drafts(output_dir, lambda latest: add_draft(latest, text))"
)
ENDPOINT_ADD_NEW = [
    "        updated = add_draft(read_drafts(output_dir), text)",
    "        write_drafts(output_dir, updated)",
]


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def join(lines: list[str], newline: str) -> str:
    return newline.join(lines) + newline


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


def segment(
    name: str, target: pathlib.Path, pairs: list[tuple[str, str]], declared: set[str]
) -> tuple[str, pathlib.Path, list[tuple[str, str]], set[str]]:
    return name, target, pairs, declared


def main() -> int:
    # 控制台 GBK 会把中文输出编成 GBK 字节，读数的 UTF-8 解码就成乱码（01 踩到过一次）
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sources = {path: path.read_bytes() for path in (ATOMIC_IO, DRAFTS, WEBAPP)}
    texts = {path: raw.decode("utf-8") for path, raw in sources.items()}
    newlines = {path: newline_of(text) for path, text in texts.items()}

    segments = [
        segment(
            "A 撤掉临界区",
            DRAFTS,
            [
                (
                    join(LOCK_BLOCK, newlines[DRAFTS]),
                    join(NO_LOCK_BLOCK, newlines[DRAFTS]),
                )
            ],
            {
                PREFIX + "test_update_drafts_does_not_lose_a_concurrent_add",
                PREFIX + "test_update_drafts_does_not_lose_a_concurrent_delete",
                PREFIX + "test_two_drafts_endpoints_do_not_clobber_each_other",
            },
        ),
        segment(
            "B 撤掉共享原语（唯一临时名 + 清残渣）",
            ATOMIC_IO,
            [
                (UNIQUE_TMP, FIXED_TMP),
                (
                    join(CLEANUP_LINES, newlines[ATOMIC_IO]),
                    join(NO_CLEANUP_LINES, newlines[ATOMIC_IO]),
                ),
            ],
            {
                PREFIX + "test_concurrent_drafts_writes_share_no_tmp_file",
                PREFIX
                + "test_drafts_write_failure_leaves_no_residue_and_keeps_the_original_error",
            },
        ),
        segment(
            "C 端点退回旧形状（绕开 update_drafts）",
            WEBAPP,
            [
                (ENDPOINT_IMPORT_OLD, ENDPOINT_IMPORT_NEW),
                (
                    ENDPOINT_ADD_OLD + newlines[WEBAPP],
                    join(ENDPOINT_ADD_NEW, newlines[WEBAPP]),
                ),
            ],
            {PREFIX + "test_two_drafts_endpoints_do_not_clobber_each_other"},
        ),
    ]

    for path in (ATOMIC_IO, DRAFTS, WEBAPP):
        print(
            f"# 被撤的源码：{path.relative_to(ROOT).as_posix()} "
            f"sha256={sha256(path)} 行尾={'CRLF' if newlines[path] == chr(13) + chr(10) else 'LF'}"
        )
    print(f"# 判据文件：{CASES} sha256={sha256(ROOT / CASES)}")
    print()

    verdicts: list[bool] = []
    for name, target, pairs, declared in segments:
        print(f"== {name} ==")
        text = texts[target]
        raw = sources[target]
        missing_anchor = [old for old, _ in pairs if old not in text]
        if missing_anchor:
            print(f"   [!] 锚点失效（源码里找不到要撤的那段）：{missing_anchor!r}——探针该修了\n")
            verdicts.append(False)
            continue
        patched = text
        for old, new in pairs:
            patched = patched.replace(old, new, 1)
        try:
            target.write_bytes(patched.encode("utf-8"))
            failed, tail = run_tests()
        finally:
            target.write_bytes(raw)

        restored = sha256(target) == hashlib.sha256(raw).hexdigest()
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
