"""contrast-residue 轮 · 「改前 / 改后」两发跑法（工单 04 的真像素取证）。

做四件事（**逐字节**，改前那一发用的是 `git show HEAD:<页面>` 的版本）：

1. 记住工作树里 `index.html` 的内容与 sha256；
2. 把它换成 `HEAD` 版本（= 本工单改之前的那一版）→ 跑探针 `--tag before`；
3. 复原（**核 sha256**，不一致就大声失败）；
4. 跑探针 `--tag after`。

跑法（仓库根）：`python .scratch\\contrast-residue\\run-before-after.py <探针文件名> [额外参数…]`
例：`python .scratch\\contrast-residue\\run-before-after.py probe-07-muted-text-pixels.mjs`
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
REL = "src/contest_generator/static/index.html"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("用法：run-before-after.py <探针文件名> [额外参数…]")
    probe = str(Path(__file__).resolve().parent / sys.argv[1])
    extra = sys.argv[2:]
    mine = PAGE.read_bytes()
    head = subprocess.run(["git", "show", f"HEAD:{REL}"], cwd=ROOT,
                          capture_output=True, check=True).stdout
    print(f"工作树 sha256 = {sha(mine)}")
    print(f"HEAD   sha256 = {sha(head)}（改前那一发用它）")
    if sha(mine) == sha(head):
        raise SystemExit("工作树与 HEAD 的页面相同——没有'改前'可量（是不是已经提交了？）")
    try:
        PAGE.write_bytes(head)
        print("\n===== 改前（HEAD 版页面）=====")
        subprocess.run(["node", probe, "--tag", "before", *extra], cwd=ROOT, check=False)
    finally:
        PAGE.write_bytes(mine)
        back = sha(PAGE.read_bytes())
        print(f"\n复原 sha256 = {back}　{'✅ 逐字节一致' if back == sha(mine) else '❌ 不一致！'}")
        if back != sha(mine):
            raise SystemExit("复原失败——页面已经不是原来的内容了")
    print("\n===== 改后（工作树版页面）=====")
    subprocess.run(["node", probe, "--tag", "after", *extra], cwd=ROOT, check=False)


if __name__ == "__main__":
    main()
