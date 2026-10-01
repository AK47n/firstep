"""发布后对账（发版 v1.4.3，工单 04/05）。

判据：**服务端八件资产的 size 与本地那八份逐件相同**（0 处不一致才算过）。
   · 本地：`%USERPROFILE%\\Desktop\\firstep-pack\\firstep-{update,full}-v1.4.3.*`
   · 服务端：`gh release view v1.4.3 --repo AK47n/firstep --json assets`（`gh` 已认证）

为什么不用 PowerShell 的 `>` 接 `gh`：那是 UTF-16LE，`json.loads` 直接炸
（本轮真踩过：`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff`）。
这里走 `subprocess.run(text=True, encoding="utf-8")`，一次收全量。

跑法（仓库根）：`python .scratch\\release-v1.4.3\\verify-assets.py`
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACK = pathlib.Path.home() / "Desktop" / "firstep-pack"
TAG = "v1.4.3"
NAMES = [
    f"firstep-update-{TAG}.zip",
    f"firstep-update-{TAG}.files.txt",
    f"firstep-update-{TAG}.removed.txt",
    f"firstep-update-{TAG}.sha256.txt",
    f"firstep-full-{TAG}.zip",
    f"firstep-full-{TAG}.manifest.json",
    f"firstep-full-{TAG}.removed.txt",
    f"firstep-full-{TAG}.sha256.txt",
]


def main() -> int:
    proc = subprocess.run(
        ["gh", "release", "view", TAG, "--repo", "AK47n/firstep", "--json", "tagName,name,assets"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        print(f"gh 取 release 失败（退出码 {proc.returncode}）：{(proc.stderr or '').strip()}")
        return 2
    data = json.loads(proc.stdout)
    print(f"Release：{data.get('name')}")
    server = {a["name"]: a["size"] for a in data.get("assets", [])}

    print("=" * 92)
    print(f"{'资产':<44}{'本地':>14}{'服务端':>14}   结果")
    print("=" * 92)
    bad = 0
    for name in NAMES:
        local_path = PACK / name
        local = local_path.stat().st_size if local_path.is_file() else None
        remote = server.get(name)
        if local is None:
            verdict = "本地缺"
        elif remote is None:
            verdict = "服务端缺"
        elif local == remote:
            verdict = "一致"
        else:
            verdict = "不一致"
        if verdict != "一致":
            bad += 1
        print(f"{name:<44}{(local if local is not None else '—'):>14}{(remote if remote is not None else '—'):>14}   {verdict}")
    print("=" * 92)
    print(f"结论：{len(NAMES) - bad}/{len(NAMES)} 一致" + ("" if bad == 0 else f"，{bad} 处不一致"))
    extra = sorted(set(server) - set(NAMES))
    if extra:
        print(f"（服务端还有清单外的资产：{extra}）")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
