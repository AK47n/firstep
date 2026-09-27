"""反证探针（工单 record-write-hardening/04）：逐段撤掉修 → 对应判据必须**点名红**。

五段（每段一类机制，逐条声明必须红 + 与实得 FAILED 对账 + 复原 sha256 逐字节）：
- **A 撤掉临界区**：`params.update_params` 里 `with path_lock(path):` → `if True:`
  （"两个 apply 交叠两条都在"的域层判据与端点判据必须红）
- **B 重读挪到锁外**：`update_params` 先把表读进 `stale`，锁里 `merge(stale)`
  （同上两条必须红——后一笔拿锁外的旧快照写回）
- **C 刷新退回旧形状**：`_persist_applied_param` 拿**开头读到的那份快照**算刷新、整份写回
  （"扫描刚落的新表不许被盖回旧快照"那条必须红；端点判据也红——它不再走临界区）
- **D 撤掉共享原语**：`atomic_io.atomic_write_text` 撤回收走前的形状——唯一临时名 → 固定名
  ＋ `finally` 清残渣 → `pass`（"写失败留残渣""并发抢临时名"两条必须红）
- **E 撤掉"无变化不写"短路**：`update_params` 里 `if param_list is not latest:` → `if True:`
  （"表在两次读之间被删掉不许凭空造空表"那条必须红）

形状照 `.scratch/record-write-hardening/probe-01-red.py`：**逐条声明**哪些用例必须红，
再把实得 `FAILED` 集合与声明对账——多出来的红如实打印，**不据此判 PASS**；
每段跑完复原源码并核对 sha256 逐字节相同（**字节往返**，不用文本模式：Windows 上
文本写会把 `\n` 翻成 `\r\n`，复原的 sha 就对不上了）。

多行锚点按**文件实际行尾**拼：本工作树被 git 碰过之后可能是 CRLF，写死 `\n` 的锚点会静默失配。

用法：`python .scratch/record-write-hardening/probe-04-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ATOMIC_IO = ROOT / "src" / "contest_generator" / "atomic_io.py"
PARAMS = ROOT / "src" / "contest_generator" / "params.py"
CASES = ["tests/test_params.py"]
PREFIX = "tests/test_params.py::"

LOCK_BLOCK = [
    "    path = params_path(output_dir)",
    "    with path_lock(path):",
    "        latest = read_params(output_dir)",
    "        param_list = merge(latest)",
]
NO_LOCK_BLOCK = [
    "    path = params_path(output_dir)",
    "    if True:",
    "        latest = read_params(output_dir)",
    "        param_list = merge(latest)",
]
READ_OUTSIDE = [
    "    path = params_path(output_dir)",
    "    stale = read_params(output_dir)",
    "    with path_lock(path):",
    "        latest = stale",
    "        param_list = merge(latest)",
]
NO_CHANGE_SHORTCUT = [
    "        if param_list is not latest:",
    "            write_params(output_dir, param_list)",
]
ALWAYS_WRITE = [
    "        if True:",
    "            write_params(output_dir, param_list)",
]
REFRESH_OLD = [
    "        update_params(",
    "            output_dir,",
    "            lambda latest: _refresh_param_after_apply(",
    "                latest, param.name, new_value, disk_main_c",
    "            ),",
    "        )",
    "    except OSError:",
    "        pass  # 写盘失败不阻断主流程",
]
REFRESH_NEW = [
    "        refreshed = _refresh_param_after_apply(",
    "            param_list, param.name, new_value, disk_main_c",
    "        )",
    "        if refreshed is not param_list:",
    "            write_params(output_dir, refreshed)",
    "    except OSError:",
    "        pass  # 写盘失败不阻断主流程",
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
    targets = (ATOMIC_IO, PARAMS)
    sources = {path: path.read_bytes() for path in targets}
    texts = {path: raw.decode("utf-8") for path, raw in sources.items()}
    newlines = {path: newline_of(text) for path, text in texts.items()}

    def lines(items: list[str], path: pathlib.Path) -> str:
        return join(items, newlines[path])

    both = {
        PREFIX + "test_update_params_does_not_lose_a_concurrent_refresh",
        PREFIX + "test_params_apply_sse_flow_serialises_with_another_refresh",
    }
    segments = [
        (
            "A 撤掉临界区",
            PARAMS,
            [(lines(LOCK_BLOCK, PARAMS), lines(NO_LOCK_BLOCK, PARAMS))],
            set(both),
        ),
        (
            "B 重读挪到锁外",
            PARAMS,
            [(lines(LOCK_BLOCK, PARAMS), lines(READ_OUTSIDE, PARAMS))],
            set(both),
        ),
        (
            "C 刷新退回旧形状（拿开头那份快照整份写回）",
            PARAMS,
            [(lines(REFRESH_OLD, PARAMS), lines(REFRESH_NEW, PARAMS))],
            {
                PREFIX
                + "test_persist_applied_param_refreshes_on_a_table_that_landed_after_the_read",
                PREFIX + "test_params_apply_sse_flow_serialises_with_another_refresh",
            },
        ),
        (
            "D 撤掉共享原语（唯一临时名 + 清残渣）",
            ATOMIC_IO,
            [
                (UNIQUE_TMP, FIXED_TMP),
                (lines(CLEANUP_LINES, ATOMIC_IO), lines(NO_CLEANUP_LINES, ATOMIC_IO)),
            ],
            {
                PREFIX + "test_params_write_failure_leaves_no_residue_and_keeps_the_original_error",
                PREFIX + "test_concurrent_params_writes_share_no_tmp_file",
            },
        ),
        (
            "E 撤掉「无变化不写」短路",
            PARAMS,
            [
                (
                    lines(NO_CHANGE_SHORTCUT, PARAMS),
                    lines(ALWAYS_WRITE, PARAMS),
                )
            ],
            {
                PREFIX
                + "test_persist_applied_param_does_not_create_a_table_that_vanished",
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
