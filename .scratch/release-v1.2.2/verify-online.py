# -*- coding: utf-8 -*-
"""线上资产核对（工单 release-v1.2.2/04）：v1.2.2 八件套齐 + `/releases/latest` 指向它。

判据（`docs/agents/releasing.md`「完整包流程」第 4 条）：
- 八件资产全在且 `state=uploaded`；
- `firstep-full-v1.2.2.zip` 在场、体积与「约 770 MB」同量级——它是**新用户唯一的安装包**；
- `firstep-full-v1.2.2.manifest.json` 在场——工具内「检查完整包」靠它发现新版本；
- `/releases/latest` == v1.2.2（已装用户点「检查更新」看的就是这个）。
"""

from __future__ import annotations

import json
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "AK47n/firstep"
TAG = "v1.2.2"

EXPECTED = [
    f"firstep-update-{TAG}.zip",
    f"firstep-update-{TAG}.files.txt",
    f"firstep-update-{TAG}.removed.txt",
    f"firstep-update-{TAG}.sha256.txt",
    f"firstep-full-{TAG}.zip",
    f"firstep-full-{TAG}.manifest.json",
    f"firstep-full-{TAG}.removed.txt",
    f"firstep-full-{TAG}.sha256.txt",
]


def gh(*args: str) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise SystemExit(f"gh 失败：{proc.stderr.strip()}")
    return proc.stdout


def main() -> int:
    ok = True
    data = json.loads(gh("release", "view", TAG, "--repo", REPO,
                         "--json", "tagName,assets"))
    by_name = {a["name"]: a for a in data["assets"]}
    print(f"# 线上核对：{TAG}")
    print(f"  资产 {len(data['assets'])} 件\n")

    for name in EXPECTED:
        asset = by_name.get(name)
        if asset is None:
            print(f"  ✗ 缺：{name}")
            ok = False
            continue
        size = int(asset["size"])
        good = asset["state"] == "uploaded" and size > 0
        print(f"  {'✓' if good else '✗'} {name:42s} {size:>12,} B  {asset['state']}")
        ok = ok and good

    extra = sorted(set(by_name) - set(EXPECTED))
    if extra:
        print(f"  （另有非本版资产：{extra}）")

    full_zip = by_name.get(f"firstep-full-{TAG}.zip")
    if full_zip:
        mb = int(full_zip["size"]) / 1024 / 1024
        in_range = 700 <= mb <= 900
        print(f"\n  完整包 zip {mb:.1f} MB（新用户唯一入口，期望「约 770 MB」同量级）："
              f"{'✓' if in_range else '✗'}")
        ok = ok and in_range

    latest = gh("api", f"repos/{REPO}/releases/latest", "--jq", ".tag_name").strip()
    print(f"  /releases/latest = {latest}：{'✓' if latest == TAG else '✗'}")
    ok = ok and latest == TAG

    print(f"\n总判：{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
