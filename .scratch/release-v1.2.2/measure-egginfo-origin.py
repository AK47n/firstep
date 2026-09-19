# -*- coding: utf-8 -*-
"""决定性实验：官方完整包里**本来没有** egg-info，是 `pip install -e .` 现写的（工单 05）。

## 为什么要这一支

drill-01 的构成判据报 `not_in_official == 6`，那 6 条全是
`src/contest_generator.egg-info/**`。两条现成证据已经指向「pip 产物」：

1. 更新器日志里这 6 条**被逐条删过**（`删除已废弃文件：…egg-info/…` 六行），随后 log 才写
   `pyproject.toml 已变化，重装依赖（pip install -e .）`——顺序本身就说明问题；
2. 其中 4 条（`dependency_links` / `entry_points` / `requires` / `top_level`）与**本机仓库**
   （从未被任何更新器碰过）的那 4 条逐字节相同。

但「与本机仓库比」这条判据有个固有缺陷：另外 2 条（`PKG-INFO` / `SOURCES.txt`）**必然**随
所在树与版本而变（`PKG-INFO` 里有版本号、`SOURCES.txt` 列的是那棵树的文件），所以它永远
不可能全等。本支换一条**与树无关**的判据，一步到位：

    **在一份刚解压的官方完整包里跑一次 `pip install -e . --no-deps`，看它会不会
     自己长出这 6 个文件。**

- 若会长出来 ⇒ 这 6 条是**安装行为**的产物，不是包内容；`not_in_official` 里出现它们
  与「盘面与全新安装一致」不矛盾（全新安装走同样的 pip 步骤，一样会有）。
- 若长不出来 ⇒ 它们真的来自包外某处，那就是个真问题，得另开单。

判据（三条必须同时成立）：

1. 解压出的树里 **egg-info 一个都没有**（证明官方包不含它）；
2. 跑完 `pip install -e . --no-deps` 之后 **6 个文件齐了、路径与沙箱那 6 条一一对应**；
3. 该子进程的 `pip` 真跑成功（退出码 0），否则"没长出来"什么都证明不了。

不联网（`--no-deps`）；沙箱与本机仓库都不碰——实验在 `%TEMP%` 下的一次性目录里做。
"""

from __future__ import annotations

import json
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
#: 沙箱那 6 条（drill 的 `not_in_official_examples`），用来比对「长出来的是不是同一批」
EXPECTED = [
    f"{REL}/PKG-INFO",
    f"{REL}/SOURCES.txt",
    f"{REL}/dependency_links.txt",
    f"{REL}/entry_points.txt",
    f"{REL}/requires.txt",
    f"{REL}/top_level.txt",
]


def main() -> int:
    if not ZIP.is_file():
        print(f"**拒绝开跑**：官方完整包不在 {ZIP}")
        return 2

    work = Path(tempfile.mkdtemp(prefix="fe05-egginfo-"))
    print(f"# 决定性实验：官方完整包里有没有 egg-info（{TAG}）")
    print(f"  一次性目录：{work}")
    try:
        # ---- 1. 只解 src/ 就够了（egg-info 的归属地）+ pyproject.toml（pip 要读）----
        print("\n## 1. 解压（只取实验需要的部分）")
        with zipfile.ZipFile(ZIP) as archive:
            wanted = [n for n in archive.namelist()
                      if n == "pyproject.toml" or n.startswith("src/")]
            archive.extractall(work, members=wanted)
        print(f"  解开条目 {len(wanted)} 个")

        before = sorted(p.relative_to(work).as_posix()
                        for p in (work / "src").rglob("*.egg-info*"))
        egg_dirs = [p for p in (work / "src").iterdir() if p.name.endswith(".egg-info")]
        print(f"  解压后 egg-info 目录：{egg_dirs}")
        print(f"  解压后 egg-info 路径命中：{len(before)}")
        ok_before = not egg_dirs and not before

        # ---- 2. 在解压出的那棵树上跑 pip install -e . --no-deps ----
        print("\n## 2. 在解压出的树上跑 `pip install -e . --no-deps`")
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".", "--no-deps",
             "--no-build-isolation", "--disable-pip-version-check"],
            cwd=str(work), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600,
        )
        pip_ok = proc.returncode == 0
        print(f"  pip 退出码 = {proc.returncode}")
        tail = [line for line in (proc.stdout or "").splitlines() if line.strip()][-4:]
        for line in tail:
            print(f"    | {line}")
        if not pip_ok:
            print(f"  stderr 末尾：{(proc.stderr or '')[-600:]}")

        # ---- 3. 长出来了吗 ----
        print("\n## 3. 跑完之后的 egg-info")
        after = sorted(p.relative_to(work).as_posix()
                       for p in (work / REL).rglob("*") if p.is_file()) \
            if (work / REL).is_dir() else []
        for path in after:
            print(f"  + {path}")
        same_set = set(after) == set(EXPECTED)

        print("\n## 判据")
        print(f"  ① 官方包里没有 egg-info：{'✓' if ok_before else '✗'}")
        print(f"  ② `pip install -e .` 跑成功：{'✓' if pip_ok else '✗'}")
        print(f"  ③ 跑完长出 6 个且路径与沙箱那 6 条一一对应：{'✓' if same_set else '✗'}"
              f"（{len(after)} 个）")
        if not same_set:
            print(f"      只在期望里：{sorted(set(EXPECTED) - set(after))}")
            print(f"      只在实测里：{sorted(set(after) - set(EXPECTED))}")
        verdict = ok_before and pip_ok and same_set
        print(f"\n  结论：egg-info 是**安装行为**的产物，不是包内容 —— "
              f"{'成立 ✓' if verdict else '**不成立 ✗**'}")
        print(f"  总判：{'PASS' if verdict else 'FAIL'}")
        return 0 if verdict else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
        print(f"\n（一次性目录已清：{work}）")


if __name__ == "__main__":
    raise SystemExit(main())
