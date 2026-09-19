# -*- coding: utf-8 -*-
"""决定性实验（v2）：**照更新器的原命令**在刚解压的官方完整包上跑一遍 pip，看 egg-info 长不长。

## v1 为什么不算数（留档，别重蹈）

v1 用的命令是 `pip install -e . --no-deps --no-build-isolation`——**多了两个更新器从不传的参数**。
`--no-build-isolation` 恰好绕开了「隔离构建」这条路径，于是 pip 走 PEP 660（只写
`__editable__*.pth` 到 site-packages，**不碰源码树**），实验里 egg-info 一个都没长出来。

而更新器的原命令是（`tools/update-app.py:285`）：

    [python, "-m", "pip", "install", "-e", str(root)]        # root 是绝对路径
    cwd = root

本支就照这一行跑，一个参数都不加。判据与 v1 相同：

1. 解压出的树里 **egg-info 一个都没有**（官方包不含它）；
2. 跑完 pip 后 **6 个文件齐了、路径与沙箱那 6 条一一对应**；
3. pip 退出码 0（否则"没长出来"什么都证明不了）。

**副作用**：这次安装会写进全局 site-packages（与沙箱那次一模一样，因为两边都没有
`.venv`、都回落到系统 python）。所以本支**必须自己收尾**：跑完 `pip uninstall -y
contest-generator`，把全局状态还原（沙箱与真身的数据目录都不碰；实验在 `%TEMP%` 下做）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACK = Path.home() / "Desktop" / "firstep-pack"
TAG = "v1.2.2"
ZIP = PACK / f"firstep-full-{TAG}.zip"
REL = "src/contest_generator.egg-info"
EXPECTED = [
    f"{REL}/PKG-INFO",
    f"{REL}/SOURCES.txt",
    f"{REL}/dependency_links.txt",
    f"{REL}/entry_points.txt",
    f"{REL}/requires.txt",
    f"{REL}/top_level.txt",
]


def pip_uninstall() -> str:
    proc = subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y",
                           "contest-generator"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    return (proc.stdout or proc.stderr or "").strip().splitlines()[-1] if (
        proc.stdout or proc.stderr) else "(无输出)"


def main() -> int:
    if not ZIP.is_file():
        print(f"**拒绝开跑**：官方完整包不在 {ZIP}")
        return 2

    print(f"# 决定性实验 v2：照更新器原命令跑 pip（{TAG}）")
    print(f"  命令：{sys.executable} -m pip install -e <解压出的根>")
    print(f"  开跑前先卸掉本机既有的 contest-generator 全局安装：{pip_uninstall()}")

    work = Path(tempfile.mkdtemp(prefix="fe05b-egginfo-"))
    print(f"  一次性目录：{work}")
    try:
        with zipfile.ZipFile(ZIP) as archive:
            wanted = [n for n in archive.namelist()
                      if n == "pyproject.toml" or n.startswith("src/")]
            archive.extractall(work, members=wanted)

        before = [p for p in (work / "src").iterdir() if p.name.endswith(".egg-info")]
        print(f"\n## 1. 解压后（{len(wanted)} 个条目）")
        print(f"  egg-info 目录：{before} → {'官方包里没有它 ✓' if not before else '✗'}")

        print("\n## 2. 照更新器原命令跑 pip（不加任何额外参数）")
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(work)],
            cwd=str(work), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=900,
        )
        pip_ok = proc.returncode == 0
        print(f"  退出码 = {proc.returncode}")
        for line in [line for line in (proc.stdout or "").splitlines() if line.strip()][-5:]:
            print(f"    | {line}")
        if not pip_ok:
            print(f"  stderr 末尾：{(proc.stderr or '')[-800:]}")

        print("\n## 3. 跑完之后的 egg-info")
        after = sorted(p.relative_to(work).as_posix()
                       for p in (work / REL).rglob("*") if p.is_file()) \
            if (work / REL).is_dir() else []
        for path in after:
            print(f"  + {path}")
        same_set = set(after) == set(EXPECTED)

        print("\n## 判据")
        ok_before = not before
        print(f"  ① 官方包里没有 egg-info：{'✓' if ok_before else '✗'}")
        print(f"  ② pip 跑成功：{'✓' if pip_ok else '✗'}")
        print(f"  ③ 跑完长出 6 个且与沙箱那 6 条一一对应：{'✓' if same_set else '✗'}"
              f"（{len(after)} 个）")
        if not same_set:
            print(f"      只在期望里：{sorted(set(EXPECTED) - set(after))}")
            print(f"      只在实测里：{sorted(set(after) - set(EXPECTED))}")
        verdict = ok_before and pip_ok and same_set
        print(f"\n  结论：egg-info 是**更新器那一步 pip** 现写的，不是包内容 —— "
              f"{'成立 ✓' if verdict else '**不成立 ✗**'}")
        print(f"  总判：{'PASS' if verdict else 'FAIL'}")
        return 0 if verdict else 1
    finally:
        # 必须自己收尾：这次安装指向下面这个一次性目录，不卸掉就会把全局状态带歪
        print(f"\n## 收尾：卸掉指向一次性目录的全局安装")
        print(f"  {pip_uninstall()}")
        shutil.rmtree(work, ignore_errors=True)
        print(f"  （一次性目录已清：{work}）")


if __name__ == "__main__":
    raise SystemExit(main())
