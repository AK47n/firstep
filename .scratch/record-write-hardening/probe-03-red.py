"""反证探针（工单 record-write-hardening/03）：逐段撤掉修 → 对应判据必须**点名红**。

四段（每段一类机制，逐条声明必须红 + 与实得 FAILED 对账 + 复原 sha256 逐字节）：

- **A 撤掉临界区**：`idea_chat.update_idea_chat` 里 `with path_lock(path):` → `if True:`
  （端点那条"send 与 adopt 串行"的判据必须红——这条是"撤锁必须变红"的端点判据）
- **B 锁键去掉文件名**：`atomic_io.path_lock` 的键 `abspath(path)` → `abspath(path.parent)`
  （同目录两份历史共用一把锁 → "两份文件不共锁"的判据必须红）
- **C 端点退回旧形状**：想法商量的 send 端点改回"模型调用前读的那份快照 → 追加 → 整份写"
  （两条端点判据必须红：慢窗口里采纳的结论被盖掉 / 两笔不串行）
- **D 重读挪到锁外**：`update_idea_chat` 先把记录读进 `stale`，锁里 `merge(stale)`
  （"跨慢窗口追加重放"的域层判据与端点判据必须红）
- **E 撤掉共享原语**：`atomic_io.atomic_write_text` 撤回收走前的形状——唯一临时名 → 固定名
  ＋ `finally` 清残渣 → `pass`（域层的"写失败留残渣""并发抢临时名"两条必须红）

形状照 `.scratch/record-write-hardening/probe-01-red.py`：**逐条声明**哪些用例必须红，
再把实得 `FAILED` 集合与声明对账——多出来的红如实打印，**不据此判 PASS**；
每段跑完复原源码并核对 sha256 逐字节相同（**字节往返**，不用文本模式：Windows 上
文本写会把 `\n` 翻成 `\r\n`，复原的 sha 就对不上了）。

多行锚点按**文件实际行尾**拼：本工作树被 git 碰过之后可能是 CRLF，写死 `\n` 的锚点会静默失配。

用法：`python .scratch/record-write-hardening/probe-03-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ATOMIC_IO = ROOT / "src" / "contest_generator" / "atomic_io.py"
IDEA_CHAT = ROOT / "src" / "contest_generator" / "idea_chat.py"
WEBAPP = ROOT / "src" / "contest_generator" / "webapp.py"
CASES = ["tests/test_idea_chat.py", "tests/test_task_progress.py"]
DOMAIN = "tests/test_idea_chat.py::"
ENDPOINT = "tests/test_task_progress.py::"

LOCK_KEY = "    key = os.path.normcase(os.path.abspath(path))"
DIR_KEY = "    key = os.path.normcase(os.path.abspath(path.parent))"

LOCK_BLOCK = [
    "    with path_lock(path):",
    "        chat = merge(read_idea_chat(output_dir, filename))",
]
NO_LOCK_BLOCK = [
    "    if True:",
    "        chat = merge(read_idea_chat(output_dir, filename))",
]
READ_INSIDE = [
    "    path = output_dir / filename",
    "    with path_lock(path):",
    "        chat = merge(read_idea_chat(output_dir, filename))",
]
READ_OUTSIDE = [
    "    path = output_dir / filename",
    "    stale = read_idea_chat(output_dir, filename)",
    "    with path_lock(path):",
    "        chat = merge(stale)",
]
ENDPOINT_IMPORT_OLD = (
    "        from .idea_chat import append_chat_round, read_idea_chat, update_idea_chat"
)
ENDPOINT_IMPORT_NEW = (
    "        from .idea_chat import append_chat_message, read_idea_chat, write_idea_chat"
)
ENDPOINT_TAIL_OLD = [
    "        updated = update_idea_chat(",
    "            output_dir,",
    "            lambda latest: append_chat_round(latest, history[-1][1], discussion.reply),",
    "        )",
    '        return {"reply": discussion.reply, "chat": updated.to_dict()}',
]
ENDPOINT_TAIL_NEW = [
    '        chat = append_chat_message(chat, "user", history[-1][1])',
    '        chat = append_chat_message(chat, "assistant", discussion.reply)',
    "        write_idea_chat(output_dir, chat)",
    '        return {"reply": discussion.reply, "chat": chat.to_dict()}',
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
    # 控制台 GBK 会把中文输出编成 GBK 字节，读数的 UTF-8 解码就成乱码（01 踩到过一次）
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    targets = (ATOMIC_IO, IDEA_CHAT, WEBAPP)
    sources = {path: path.read_bytes() for path in targets}
    texts = {path: raw.decode("utf-8") for path, raw in sources.items()}
    newlines = {path: newline_of(text) for path, text in texts.items()}

    def lines(items: list[str], path: pathlib.Path) -> str:
        return join(items, newlines[path])

    segments = [
        (
            "A 撤掉临界区",
            IDEA_CHAT,
            [(lines(LOCK_BLOCK, IDEA_CHAT), lines(NO_LOCK_BLOCK, IDEA_CHAT))],
            {
                DOMAIN + "test_update_idea_chat_keeps_an_adopt_that_landed_in_the_slow_window",
                ENDPOINT + "test_idea_chat_send_and_adopt_serialise_their_record_writes",
            },
        ),
        (
            "B 锁键去掉文件名",
            ATOMIC_IO,
            [(LOCK_KEY, DIR_KEY)],
            {DOMAIN + "test_two_chat_files_do_not_share_a_lock"},
        ),
        (
            "C 端点退回旧形状（读旧快照 → 整份写）",
            WEBAPP,
            [
                (ENDPOINT_IMPORT_OLD, ENDPOINT_IMPORT_NEW),
                (
                    lines(ENDPOINT_TAIL_OLD, WEBAPP),
                    lines(ENDPOINT_TAIL_NEW, WEBAPP),
                ),
            ],
            {
                ENDPOINT
                + "test_idea_chat_send_keeps_an_adopt_that_landed_during_the_model_call",
                ENDPOINT + "test_idea_chat_send_and_adopt_serialise_their_record_writes",
            },
        ),
        (
            "D 重读挪到锁外",
            IDEA_CHAT,
            [(lines(READ_INSIDE, IDEA_CHAT), lines(READ_OUTSIDE, IDEA_CHAT))],
            {
                DOMAIN + "test_update_idea_chat_keeps_an_adopt_that_landed_in_the_slow_window",
                ENDPOINT + "test_idea_chat_send_and_adopt_serialise_their_record_writes",
            },
        ),
        (
            "E 撤掉共享原语（唯一临时名 + 清残渣）",
            ATOMIC_IO,
            [
                (UNIQUE_TMP, FIXED_TMP),
                (
                    lines(CLEANUP_LINES, ATOMIC_IO),
                    lines(NO_CLEANUP_LINES, ATOMIC_IO),
                ),
            ],
            {
                DOMAIN
                + "test_idea_chat_write_failure_leaves_no_residue_and_keeps_the_original_error",
                DOMAIN + "test_concurrent_idea_chat_writes_share_no_tmp_file",
            },
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
