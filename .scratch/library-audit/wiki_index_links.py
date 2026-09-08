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
import urllib.error
import urllib.request

INDEX_URLS = (
    "https://wiki.lckfb.com/zh-hans/dmx/module/",
    "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/",
)

# 全站扩面（工单 04「05 续」）：除 dmx / dkx 外还扫过的板族——用来证明
# 「索引里没有该器件页」是全站结论，而不是只看了两个板。
ALL_BOARD_INDEX_URLS = (
    *INDEX_URLS,
    "https://wiki.lckfb.com/zh-hans/dzx-mspm0l1306/module/",
    "https://wiki.lckfb.com/zh-hans/tmx-mspm0g3507/module/",
    "https://wiki.lckfb.com/zh-hans/tqx-mspm0g3519/module/",
    "https://wiki.lckfb.com/zh-hans/gd32e230c8t6/module/",
    "https://wiki.lckfb.com/zh-hans/tjx-tms320f28p550/module/",
    "https://wiki.lckfb.com/zh-hans/coloreasyduino/module/",
)

LINK_RE = re.compile(
    r'href="(/zh-hans/(?:dmx|dkx-stm32f103c8t6)/[^"#?]+\.html)"'
)
ANY_LINK_RE = re.compile(r'href="(/zh-hans/[^"#?]+\.html)"')


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


def all_board_links() -> dict[str, list[str]]:
    """全站各板模块手册索引页的站内链接：{板族名: 去重排序链接}。

    只保留 `/module/` 路径下的手册页链接（排除导航与入门教程），
    取不到索引页的板（如 tqx 模块索引 404）返回空列表。
    """
    result: dict[str, list[str]] = {}
    for url in ALL_BOARD_INDEX_URLS:
        board = url.split("/zh-hans/")[1].split("/")[0]
        try:
            body = fetch(url)
        except urllib.error.HTTPError:
            result[board] = []
            continue
        result[board] = sorted(
            {
                link
                for link in ANY_LINK_RE.findall(body)
                if f"/{board}/module/" in link
            }
        )
    return result


def main() -> int:
    links = index_links()
    print(f"索引页模块手册链接 {len(links)} 条")
    for link in links:
        print("  " + link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
