"""核对某个 Release 当前已上传的资产（默认 v1.1.1，可用 argv[1] 指定 tag）。"""

from __future__ import annotations

import json
import subprocess
import sys

TAG = sys.argv[1] if len(sys.argv) > 1 else "v1.1.1"

result = subprocess.run(
    ["gh", "release", "view", TAG, "--repo", "AK47n/firstep",
     "--json", "assets,tagName,isDraft,url"],
    capture_output=True, text=True, encoding="utf-8-sig",
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
