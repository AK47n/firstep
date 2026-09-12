"""核对 v1.1.0 Release 当前已上传的资产。"""

from __future__ import annotations

import json
import subprocess

result = subprocess.run(
    ["gh", "release", "view", "v1.1.0", "--repo", "AK47n/firstep",
     "--json", "assets,tagName,isDraft,url"],
    capture_output=True, text=True, encoding="utf-8",
)
if result.returncode != 0:
    print("gh 失败：", result.stderr[:300])
    raise SystemExit(1)
data = json.loads(result.stdout)
print("tag:", data["tagName"], "| draft:", data["isDraft"], "|", data["url"])
if not data["assets"]:
    print("（还没有资产）")
for asset in data["assets"]:
    print(f"  {asset['name']:45} {asset['size'] / 1048576:8.2f} MB")
