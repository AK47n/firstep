# -*- coding: utf-8 -*-
"""反证：排序之后那条并发用例**还咬得住**"固定临时名"这个真缺陷吗？（工单 backlog-agent-sweep/01）

做法（照本仓库既有反证探针的纪律）：
  1. **前置干净性检查**：`src/contest_generator/atomic_io.py` 当前必须是**唯一临时名**那一版；
  2. 把临时名那一行**注入**回旧形态（固定 `<名>.tmp`），逐字节写盘；
  3. 子进程跑 `pytest tests/test_hwcheck_triage.py::test_concurrent_record_writes_share_no_tmp_file`；
     判据 = **必须红**，且失败信息指向"并发写报错/残留"（不是超时之类的判据自身失败）；
  4. `finally` 里**逐字节复原**并复核 sha256 一致（被强杀也留下"复原命令"的提示）。

⚠ 它会**真的改库内文件**（约 1 秒）——**别与任何套件/门禁同时跑**。
用法：`python .scratch/backlog-agent-sweep/probe-01-reverse.py`
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TARGET = REPO / "src/contest_generator/atomic_io.py"
TEST_ID = "tests/test_hwcheck_triage.py::test_concurrent_record_writes_share_no_tmp_file"

NEW_LINE = 'tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}")'
OLD_LINE = 'tmp = path.with_name(f"{path.name}.tmp")'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    original = TARGET.read_bytes()
    before = sha256(original)
    nl = b"\r\n" if b"\r\n" in original else b"\n"
    print(f"前置：{TARGET.name} sha256 = {before[:16]}…（换行 {'CRLF' if nl == b'\\r\\n' else 'LF'}）")

    # ① 前置干净性检查：锚点必须恰好命中一次
    anchor = NEW_LINE.encode("utf-8")
    if original.count(anchor) != 1:
        print(f"✗ 前置不成立：唯一临时名锚点命中 {original.count(anchor)} 次（应为 1）——先看盘上是什么")
        return 2

    status = 1
    try:
        # 锚点是**行内子串**（不含前导缩进），所以替换串也不带缩进——带了就双缩进、
        # 注入出来的是 IndentationError（第一版就是这么错的，红是红了，但红在语法上，
        # 判据"失败指向被测机制"当场把它抓下来）。
        injected = original.replace(anchor, OLD_LINE.encode("utf-8"))
        assert injected != original, "注入没生效"
        # 写盘保持原换行（这里是单行替换，不新增行，换行天然不变）
        TARGET.write_bytes(injected)
        print(f"已注入旧形态：{OLD_LINE.strip()}")

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", TEST_ID, "-q", "-p", "no:cacheprovider"],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        body = (proc.stdout or "") + (proc.stderr or "")
        red = proc.returncode != 0
        # 失败要指向被测机制（'并发写报错' 或 '残留'），而不是判据自己超时
        on_mechanism = ("并发写报错" in body) or ("残留" in body) or ("PermissionError" in body)
        tail = [ln for ln in body.splitlines() if ln.strip()][-6:]
        print(f"注入后 pytest 退出码 = {proc.returncode}（红 = {red}；失败指向被测机制 = {on_mechanism}）")
        for ln in tail:
            print(f"    {ln}")
        if red and on_mechanism:
            print("✅ 反证成立：固定临时名形态下这条用例判红")
            status = 0
        else:
            print("✗ 反证不成立：注入旧形态之后它没有按预期红——排序可能把判据削弱了")
    finally:
        TARGET.write_bytes(original)
        after = sha256(TARGET.read_bytes())
        ok = after == before
        print(f"复原复核：sha256 {'一致 ✅' if ok else '不一致 ✗'}（{after[:16]}…）")
        if not ok:
            print(f"  手工复原：git checkout -- {TARGET.relative_to(REPO).as_posix()}")
            status = 2
    return status


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
