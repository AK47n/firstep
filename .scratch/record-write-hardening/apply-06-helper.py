"""收口迁移脚本（工单 record-write-hardening/06）：把四份 `_run_in_thread` 复制换成共享小工具。

做三件事（逐字节读、逐字节写，不让文本模式的换行归一搅进来）：
1. 删掉各文件里的 `_run_in_thread` 定义；
2. 调用点改名 `_run_in_thread(` → `run_in_thread(`；
3. 补 `from tests.concurrency import run_in_thread`（挂在 `from tests.` 块前；没有该块就挂在
   最后一个 `from contest_generator.` 导入之后）。

用法：`python .scratch/record-write-hardening/apply-06-helper.py`
"""

from __future__ import annotations

import pathlib
import re
import sys

FILES = [
    "tests/test_drafts.py",
    "tests/test_idea_chat.py",
    "tests/test_params.py",
    "tests/test_master_store.py",
]
DEF_PATTERN = re.compile(
    r"\r?\n\r?\ndef _run_in_thread\(.*?\r?\n(?:.*?\r?\n)*?    return thread\r?\n", re.S
)
IMPORT_LINE = "from tests.concurrency import run_in_thread"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name in FILES:
        path = pathlib.Path(name)
        text = path.read_bytes().decode("utf-8")
        if IMPORT_LINE in text and "_run_in_thread" not in text:
            print(f"{name}: 已迁移过，跳过")
            continue
        # 工作树可能是 CRLF（git 碰过就翻），锚点与插入行都按**文件实际行尾**走
        newline = "\r\n" if "\r\n" in text else "\n"
        stripped, count = DEF_PATTERN.subn(newline, text)
        assert count == 1, f"{name}: 找到 {count} 处 _run_in_thread 定义（应恰好 1 处）"
        assert "_run_in_thread" in stripped, f"{name}: 调用点不见了？"
        new = stripped.replace("_run_in_thread(", "run_in_thread(")
        assert "_run_in_thread" not in new, f"{name}: 还有残留"
        import_line = IMPORT_LINE + newline
        if import_line in new:
            raise SystemExit(f"{name}: 已经补过 import 了")
        anchor = re.search(r"^from tests\.", new, re.M)
        if anchor is None:
            last = None
            for match in re.finditer(r"^from contest_generator\..*$", new, re.M):
                last = match
            assert last is not None, f"{name}: 找不到可挂 import 的位置"
            at = last.end() + len(newline)
        else:
            at = anchor.start()
        new = new[:at] + import_line + new[at:]
        path.write_bytes(new.encode("utf-8"))
        print(
            f"{name}: 收成共享小工具（行尾 {'CRLF' if newline == chr(13) + chr(10) else 'LF'}，"
            f"调用点余 {new.count('run_in_thread(')} 处）"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
