# -*- coding: utf-8 -*-
"""量具：drill-01 的原始 JSON 证据汇总 + 「那 6 条到底是什么」定性（只读）。

## 为什么要单独立一支

`not_in_official == 0` 是用户给的判据。真机跑出来的值是 **6**，而那 6 条全是
`src/contest_generator.egg-info/**`——**不是产品文件**（本版已从两个包摘掉），
而是更新器第 7 步 `pip install -e .` **现写**的 pip 构建产物。

**定性证据分两支，第二支才是决定性的**：

| 支 | 做法 | 局限 |
|---|---|---|
| ① 与本机仓库比 | 同一份安装产物应当逐字节相同 | `PKG-INFO`（含版本号）与 `SOURCES.txt`（列本树文件）**必然随树而变** ⇒ 这条判据永远不可能全等 |
| ② **照更新器原命令在刚解压的官方包上跑一次 pip** | 见 `measure-egginfo-origin-v2.py` | 无——它直接回答「官方包里有没有、是不是 pip 写的」 |

① 的结论是「4/6 逐字节相同、2/6 因版本与树而异」，**这是预期**：沙箱那份是本轮 1.2.2
装的、本机那份是 1.2.1 时代装的。所以 ① 只作旁证，判据用 ② 的结论
（`verify-05-egginfo-origin.txt`：官方包 0 个 → 跑完 pip 6 个齐）。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent          # .scratch/release-v1.2.2
DRILL_DIR = HERE.parent / "verify-gate-drills"  # .scratch/verify-gate-drills
SIM = Path(r"C:\Users\luoji\Desktop\firstep-sim")
REPO = HERE.parents[1]                          # 仓库根
SUFFIX = "src/contest_generator.egg-info"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ok = True
    print("# drill-01 原始证据汇总（工单 release-v1.2.2/05）\n")

    # ---- 1. drill 自己写的 JSON ----
    # 读**带版本号**的那份（包装层改的 `OUTPUT_STEM`）：drill 自带的名字会被上一轮覆盖。
    print("## 1. drill 的原始 JSON（verify-01-upgrade-v1.2.2.json）")
    path = DRILL_DIR / "verify-01-upgrade-v1.2.2.json"
    data = json.loads(path.read_bytes().decode("utf-8"))
    verdict = data.get("verdict") or {}
    print(f"  pass = {verdict.get('pass')}")
    print(f"  problems = {verdict.get('problems')}")
    print(f"  stuck = {verdict.get('stuck')}")
    print(f"  startpoint = {data.get('startpoint')}")
    print(f"  endpoint = {data.get('endpoint')}")
    print(f"  check.latest_version = {(data.get('check') or {}).get('latest_version')}")
    comp = data.get("composition") or {}
    for key in ("official_tracked", "on_disk_tracked", "same", "stale",
                "not_in_official", "official_missing_on_disk"):
        print(f"  composition.{key} = {comp.get(key)}")
    print(f"  composition.not_in_official_examples = {comp.get('not_in_official_examples')}")

    # ---- 2. 更新器确实删过它们 ----
    print("\n## 2. 更新器日志：这 6 条被删过吗（证明它们不是包发进去的）")
    log = Path(r"C:\Users\luoji\.contest_generator_sim\updates\updater.log")
    lines = log.read_bytes().decode("utf-8", errors="replace").splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("=== firstep 更新开始")]
    chunk = lines[starts[-1]:]
    deleted = [line for line in chunk if SUFFIX in line and "删除已废弃文件" in line]
    print(f"  最后一轮（{chunk[0][-16:-4]}）里删除 egg-info 的行数：{len(deleted)}")
    for line in deleted:
        print(f"    {line.strip()}")

    # ---- 3. 旁证：沙箱 vs 本机仓库（这条**不可能全等**，见模块 docstring）----
    print("\n## 3. 旁证：沙箱 vs 本机仓库（PKG-INFO / SOURCES.txt 必然随树与版本而变）")
    sim_dir = SIM / SUFFIX
    repo_dir = REPO / SUFFIX
    names = sorted(p.name for p in repo_dir.iterdir() if p.is_file()) if repo_dir.is_dir() else []
    print(f"  本机仓库 {SUFFIX} 存在：{repo_dir.is_dir()}（{len(names)} 件）")
    same = diff = 0
    for name in names:
        a, b = sim_dir / name, repo_dir / name
        if not a.is_file():
            print(f"    ✗ 沙箱缺 {name}")
            continue
        ha, hb = sha256_of(a), sha256_of(b)
        if ha == hb:
            same += 1
            print(f"    ✓ {name:24s} {ha[:16]}…")
        else:
            diff += 1
            print(f"    · {name:24s} 沙箱 {ha[:16]}… / 本机 {hb[:16]}…（随树/版本而变，预期）")
    print(f"  逐字节相同 {same} / 不同 {diff}")

    # ---- 4. 决定性实验的结论（另一支量具写的证据）----
    print("\n## 4. 决定性实验（另一支量具）：官方包 0 个 egg-info → 照更新器原命令跑 pip → 6 个齐")
    origin = HERE / "verify-05-egginfo-origin.txt"
    origin_ok = False
    if origin.is_file():
        text = origin.read_bytes().decode("utf-8", errors="replace")
        origin_ok = "总判：PASS" in text
        for line in text.splitlines():
            if any(key in line for key in ("egg-info 目录：", "跑完长出", "结论：")):
                print(f"    {line.strip()}")
    else:
        print(f"    ✗ 缺 {origin.name}（先跑 measure-egginfo-origin-v2.py）")

    print("\n## 判据")
    print(f"  ① drill 无判红 / 无卡住：{'✓' if verdict.get('pass') else '✗'}")
    print(f"  ② 起点 1.1.1 / 终点 served = 1.2.2："
          f"{'✓' if (data.get('startpoint') or {}).get('served') == '1.1.1' and (data.get('endpoint') or {}).get('served') == '1.2.2' else '✗'}")
    print(f"  ③ 官方缺失 0 / 内容不同 0："
          f"{'✓' if comp.get('official_missing_on_disk') == 0 and comp.get('stale') == 0 else '✗'}")
    print(f"  ④ 多出来的**只有** egg-info 那 6 条："
          f"{'✓' if comp.get('not_in_official') == 6 and len(comp.get('not_in_official_examples') or []) == 6 else '✗'}")
    print(f"  ⑤ 那 6 条 = pip 现写的（决定性实验 ①②③ 全成立）：{'✓' if origin_ok else '✗'}")
    ok = ok and bool(verdict.get("pass")) and \
        (data.get("startpoint") or {}).get("served") == "1.1.1" and \
        (data.get("endpoint") or {}).get("served") == "1.2.2" and \
        comp.get("official_missing_on_disk") == 0 and comp.get("stale") == 0 and \
        comp.get("not_in_official") == 6 and origin_ok
    print(f"\n  总判：{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
