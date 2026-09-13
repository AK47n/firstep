"""对比真身 install.bat 与演练根那份（工单 newuser-download/07 排障用）。

起因：验证脚本里的 `REPO_BAT` 路径算错一层，把「测试版（看标记文件）」覆盖进了真身文件，
导致真身 `install.bat` 跑到 Python 检查那步静默退出。这个脚本把两份**逐行对齐**，
直接指出多/少/改了哪几行，不靠肉眼。
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2] / "install.bat"
GOOD = Path(os.environ["TEMP"]) / "firstep-l3" / "tool" / "install.bat"


def main() -> int:
    left = REPO.read_bytes().decode("gbk").splitlines()
    right = GOOD.read_bytes().decode("gbk").splitlines()
    print(f"真身：{len(left)} 行 / {REPO.stat().st_size} 字节")
    print(f"演练根（可用的那份）：{len(right)} 行 / {GOOD.stat().st_size} 字节")
    print()
    diff = list(difflib.unified_diff(right, left, fromfile="可用版", tofile="真身", lineterm="", n=2))
    if not diff:
        print("两份一致")
        return 0
    for line in diff:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
