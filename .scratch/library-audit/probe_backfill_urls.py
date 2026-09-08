"""回填的 source_url 存在性实测（工单 identity-fields/03 证据）。

对本次回填涉及的全部 URL 做 HEAD 请求，打印状态码——「链接不许编造」的机械证据。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/probe_backfill_urls.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"

BACKFILLED = {
    "motor": ("mspm0",),
    "xunji": ("mspm0",),
    "pid": ("mspm0", "stm32"),
    "oled": ("mspm0", "stm32"),
    "servo": ("mspm0",),
    "k230": ("mspm0", "stm32"),
}


def head(url: str) -> str:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return str(response.status)
    except Exception as exc:  # noqa: BLE001
        return f"ERR {exc}"


def main() -> int:
    failed = 0
    for slug, platforms in BACKFILLED.items():
        data = json.loads((MODULES / slug / "manifest.json").read_text(encoding="utf-8"))
        for platform in platforms:
            entry = data["platforms"][platform]
            url = entry["source_url"]
            status = head(url)
            if status != "200":
                failed += 1
            print(f"{slug}/{platform}  {status}  {url}")
            print(f"    kit: {entry['kit'][:90]}")
    print(f"=== 非 200：{failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
