"""从 lckfb wiki 模块索引页抽取「模块手册」条目链接（工单 identity-fields/03-04 取源核实）。

用法：
  $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/wiki_index_links.py

索引页**在线抓取**（不落盘快照，避免仓库里塞 HTML）；抽取规则
`href="/zh-hans/<board>/module/<category>/<slug>.html"`——手册页正文链接，
排除导航与其它板页。probe_backlog_sources.py 复用同一抓取函数。
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

INDEX_URLS = (
    "https://wiki.lckfb.com/zh-hans/dmx/module/",
    "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/",
)

LINK_RE = re.compile(
    r'href="(/zh-hans/(?:dmx|dkx-stm32f103c8t6)/[^"#?]+\.html)"'
)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "firstep-wiki-probe"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def index_links() -> list[str]:
    """两个平台的模块手册索引页全部站内链接（去重排序）。"""
    links: list[str] = []
    for url in INDEX_URLS:
        links.extend(LINK_RE.findall(fetch(url)))
    return sorted(set(links))


def main() -> int:
    links = index_links()
    print(f"索引页模块手册链接 {len(links)} 条")
    for link in links:
        print("  " + link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
