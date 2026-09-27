"""反证探针（工单 backlog-closeout/05）：逐段撤掉修 → 对应判据必须**点名红**。

五段（每段一类机制，逐条声明必须红 + 与实得 FAILED 对账 + 复原 sha256 逐字节）：

- **A 撤掉原子入口**：`entry_store.write_json_atomic` 退回裸写（`atomic_write_text` →
  直接 `write_text` 到目标文件）→ **六条判据全红**（三库的「写失败」与「强杀」两两）。
  这是本单的头条：判据挂的正是「落的这一步是原子的」。
- **B 模块库那处退回裸写**：`library._write_manifest` 的 `write_json_atomic(` → `write_json(`）
  → 模块库两条红（逐处归因：不是"某一处改了就好"）。
- **C 参考库那处退回裸写**：`reference_library.update_reference` 的元数据那一步同上
  → 参考库两条红。
- **D 赛题库那处退回裸写**：`topic_library.update_topic` 的 manifest 那一步同上
  → 赛题库两条红。
- **E 撤共享原语的清残渣**：`atomic_io.atomic_write_via` 的 `finally` 清残渣 → `pass`
  → 三条「写失败零杂散」红（强杀那三条**不**声明：强杀模拟里 `finally` 清不清得到
  不是判据——真 SIGKILL 连 `finally` 都不跑，判据只取"条目仍读得出来"）。

形状照 `.scratch/record-write-hardening/probe-03-red.py`：**逐条声明**哪些用例必须红，
再把实得 `FAILED` 与声明对账（多出来的红如实打印）；每段跑完复原源码并核对 sha256
逐字节相同（**字节往返**，不用文本模式：Windows 上文本写会把 `\n` 翻成 `\r\n`）。

多行锚点按**文件实际行尾**拼：本工作树被 git 碰过之后可能是 CRLF，写死 `\n` 的锚点会静默失配。

用法：`python .scratch/backlog-closeout/probe-05-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "contest_generator"
ATOMIC_IO = SRC / "atomic_io.py"
ENTRY_STORE = SRC / "entry_store.py"
LIBRARY = SRC / "library.py"
REFERENCE = SRC / "reference_library.py"
TOPIC = SRC / "topic_library.py"

MODULE = "tests/test_library.py::"
REF = "tests/test_reference_library.py::"
TOPIC_TESTS = "tests/test_topic_library.py::"
M_FAIL = MODULE + "test_update_platform_identity_meta_write_failure_leaves_module_intact"
M_KILL = MODULE + "test_update_platform_identity_survives_a_kill_mid_write"
R_FAIL = REF + "test_update_reference_meta_write_failure_leaves_entry_intact"
R_KILL = REF + "test_update_reference_survives_a_kill_mid_meta_write"
T_FAIL = TOPIC_TESTS + "test_update_topic_meta_write_failure_leaves_entry_intact"
T_KILL = TOPIC_TESTS + "test_update_topic_survives_a_kill_mid_meta_write"
# 判据文件（跑的就是这六条；本探针只反证本单新增的判据，定向/全量读数另跑）
CRITERIA_FILES = ("tests/test_library.py", "tests/test_reference_library.py",
                  "tests/test_topic_library.py")
CASES = [M_FAIL, M_KILL, R_FAIL, R_KILL, T_FAIL, T_KILL]
ALL_SIX = set(CASES)

# --- A：entry_store 的原子入口退回裸写 ---------------------------------------
ATOMIC_ENTRY = "    atomic_write_text(entry_dir / filename, _json_text(data))"
BARE_ENTRY = "    (entry_dir / filename).write_text(_json_text(data), encoding=\"utf-8\")"

# --- B/C/D：三处调用点各自退回裸写 -------------------------------------------
LIBRARY_ATOMIC = "    write_json_atomic(module_dir, MANIFEST_FILENAME, manifest.to_dict())"
LIBRARY_BARE = "    write_json(module_dir, MANIFEST_FILENAME, manifest.to_dict())"
REFERENCE_ATOMIC = (
    "        write_json_atomic(entry_dir, REFERENCE_META_FILENAME, new_entry.to_dict())"
)
REFERENCE_BARE = "        write_json(entry_dir, REFERENCE_META_FILENAME, new_entry.to_dict())"
TOPIC_ATOMIC_LINES = [
    "        write_json_atomic(",
    "            entry_dir,",
    "            MANIFEST_FILENAME,",
]
TOPIC_BARE_LINES = [
    "        write_json(",
    "            entry_dir,",
    "            MANIFEST_FILENAME,",
]

# --- E：共享原语的清残渣 -----------------------------------------------------
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


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def join(lines: list[str], newline: str) -> str:
    return newline.join(lines) + newline


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
    targets = (ATOMIC_IO, ENTRY_STORE, LIBRARY, REFERENCE, TOPIC)
    sources = {path: path.read_bytes() for path in targets}
    texts = {path: raw.decode("utf-8") for path, raw in sources.items()}
    newlines = {path: newline_of(text) for path, text in texts.items()}

    def lines(items: list[str], path: pathlib.Path) -> str:
        return join(items, newlines[path])

    segments = [
        (
            "A 撤掉原子入口（entry_store 退回裸写）",
            ENTRY_STORE,
            [(ATOMIC_ENTRY, BARE_ENTRY)],
            ALL_SIX,
        ),
        (
            "B 模块库那处退回裸写",
            LIBRARY,
            [(LIBRARY_ATOMIC, LIBRARY_BARE)],
            {M_FAIL, M_KILL},
        ),
        (
            "C 参考库那处退回裸写",
            REFERENCE,
            [(REFERENCE_ATOMIC, REFERENCE_BARE)],
            {R_FAIL, R_KILL},
        ),
        (
            "D 赛题库那处退回裸写",
            TOPIC,
            [
                (
                    lines(TOPIC_ATOMIC_LINES, TOPIC),
                    lines(TOPIC_BARE_LINES, TOPIC),
                )
            ],
            {T_FAIL, T_KILL},
        ),
        (
            "E 撤共享原语的清残渣",
            ATOMIC_IO,
            [(lines(CLEANUP_LINES, ATOMIC_IO), lines(NO_CLEANUP_LINES, ATOMIC_IO))],
            {M_FAIL, R_FAIL, T_FAIL},
        ),
    ]

    for path in targets:
        print(
            f"# 被撤的源码：{path.relative_to(ROOT).as_posix()} "
            f"sha256={sha256(path)} 行尾={'CRLF' if newlines[path] == chr(13) + chr(10) else 'LF'}"
        )
    for case in CRITERIA_FILES:
        print(f"# 判据文件：{case} sha256={sha256(ROOT / case)}")
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
    print("结论：" + ("PASS（五段反证全成立）" if ok else "不成立，见上"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
