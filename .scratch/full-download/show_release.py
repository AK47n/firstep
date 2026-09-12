"""一次性脚本：列出 v1.0.0 Release 的资产与说明（发版前核对既有口径）。"""

from __future__ import annotations

import json
import subprocess

result = subprocess.run(
    ["gh", "release", "view", "v1.0.0", "--repo", "AK47n/firstep", "--json",
     "name,tagName,isDraft,publishedAt,assets,body"],
    capture_output=True, text=True, encoding="utf-8",
)
if result.returncode != 0:
    print("gh 失败：", result.stderr[:400])
    raise SystemExit(1)
data = json.loads(result.stdout)
print("name:", data.get("name"))
print("tag:", data.get("tagName"), "| published:", data.get("publishedAt"), "| draft:", data.get("isDraft"))
for asset in data.get("assets", []):
    print(f"  asset: {asset['name']}  {round(asset['size'] / 1048576, 1)} MB")
print("--- body (前 600 字) ---")
print((data.get("body") or "")[:600])
