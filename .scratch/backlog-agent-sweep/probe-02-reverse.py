# -*- coding: utf-8 -*-
"""反证：新加的三条判据**咬得住**"固定临时名 + 无 finally"那个旧形态吗？（工单 backlog-agent-sweep/02）

做法（与 `probe-01-reverse.py` 同一套纪律）：
  1. **前置干净性检查**：`tools/update-app.py` 当前必须是唯一临时名那一版（锚点命中恰好一次）；
  2. 把 `extract_zip` 的写盘段落**注入**回旧形态（固定 `<目标>.update-tmp` + 无 `finally`）；
  3. 子进程跑本单新加的三条用例：判据 = **至少两条按预期红**
     （① 失败留残渣 ② 同进程两次临时名相撞），且失败信息指向被测机制；
  4. `finally` 里**逐字节复原**并复核 sha256 一致。

⚠ 它会**真的改库内文件**（约 1 秒）——**别与任何套件/门禁同时跑**。
用法：`python .scratch/backlog-agent-sweep/probe-02-reverse.py`
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TARGET = REPO / "tools/update-app.py"

NEW_BLOCK = """            tmp = target.with_name(
                f"{target.name}.{os.getpid()}-{next(_TMP_COUNTER)}.update-tmp"
            )
            try:
                with archive.open(member) as source, open(tmp, "wb") as dest:
                    shutil.copyfileobj(source, dest)
                os.replace(tmp, target)
            finally:
                # `replace` 成功时 tmp 已经不在了；失败时它还在，清掉它。
                # 清不掉也**不许**把原异常盖掉（照 atomic_io 的同一条边界）。
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:  # pragma: no cover —— 盘被占住这类
                        pass
"""

OLD_BLOCK = """            tmp = target.with_name(target.name + ".update-tmp")
            with archive.open(member) as source, open(tmp, "wb") as dest:
                shutil.copyfileobj(source, dest)
            os.replace(tmp, target)
"""

TEST_IDS = [
    "tests/test_update_app.py::test_extract_zip_failure_leaves_no_tmp_and_keeps_old_content",
    "tests/test_update_app.py::test_extract_zip_temp_names_do_not_collide_within_one_process",
    "tests/test_update_app.py::test_extract_zip_writes_content_and_leaves_no_tmp",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    original = TARGET.read_bytes()
    before = sha256(original)
    nl = "\r\n" if b"\r\n" in original else "\n"
    print(f"前置：update-app.py sha256 = {before[:16]}…（换行 {'CRLF' if nl == chr(13) + chr(10) else 'LF'}）")

    anchor = NEW_BLOCK.replace("\n", nl).encode("utf-8")
    if original.count(anchor) != 1:
        print(f"✗ 前置不成立：唯一临时名段落锚点命中 {original.count(anchor)} 次（应为 1）")
        return 2

    status = 1
    try:
        injected = original.replace(anchor, OLD_BLOCK.replace("\n", nl).encode("utf-8"))
        assert injected != original
        TARGET.write_bytes(injected)
        print("已注入旧形态：固定 `<目标>.update-tmp` + 无 finally")

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *TEST_IDS, "-q", "-p", "no:cacheprovider"],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        body = (proc.stdout or "") + (proc.stderr or "")
        failed = [ln for ln in body.splitlines() if ln.startswith("FAILED ")]
        on_mechanism = ("留下了临时文件" in body) or ("用了同一个临时名" in body)
        print(f"注入后 pytest 退出码 = {proc.returncode}；红 {len(failed)} 条：")
        for ln in failed:
            print(f"    {ln}")
        if len(failed) >= 2 and on_mechanism:
            print("✅ 反证成立：旧形态下新判据按预期红（残渣 + 临时名相撞）")
            status = 0
        else:
            print("✗ 反证不成立：注入旧形态之后新判据没有按预期红")
    finally:
        TARGET.write_bytes(original)
        after = sha256(TARGET.read_bytes())
        ok = after == before
        print(f"复原复核：sha256 {'一致 ✅' if ok else '不一致 ✗'}（{after[:16]}…）")
        if not ok:
            print("  手工复原：git checkout -- tools/update-app.py")
            status = 2
    return status


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
