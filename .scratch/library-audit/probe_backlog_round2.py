"""待补器件第二轮取源核实（工单 identity-fields/04 续）。

对 7 个待补 slug 逐条找**可核实**出处：
  ① 立创 wiki 索引页（dmx + dkx 模块手册 / 入门教程）里有哪些相关页；
  ② 立创商城搜索接口里有没有对应实物（可作 source_url 的商城商品页）；
  ③ 本地手册原文里的厂商线索（DL-20 / DCC-100v3 说明书）。

用法：
  $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/probe_backlog_round2.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wiki_index_links import fetch, index_links  # noqa: E402

# 立创商城搜索（公开站点，返回 HTML/JSON；仅用于「实物是否存在」的核实）
LCSC_SEARCH = "https://so.szlcsc.com/global.html?k={kw}"

QUERIES: dict[str, tuple[str, ...]] = {
    "beep": ("蜂鸣器模块", "有源蜂鸣器"),
    "ir_beam": ("红外对射", "红外光电对射模块"),
    "key": ("轻触按键模块",),
    "led": ("LED模块",),
    "step_motor": ("DCC-100", "闭环步进电机"),
    "zigbee_link": ("DL-20", "zigbee串口透传模块"),
}

EXTERNAL_HINTS = ("taobao", "tmall", "szlcsc", "detail.", "item.", "jd.com")


def _page_links(url: str) -> list[str]:
    html = fetch(url)
    return sorted(
        {
            link
            for link in re.findall(r'https?://[^"\'<>\\ ]+', html)
            if any(hint in link for hint in EXTERNAL_HINTS)
        }
    )


def _lcsc_search(keyword: str) -> str:
    url = LCSC_SEARCH.format(kw=urllib.parse.quote(keyword))
    request = urllib.request.Request(url, headers={"User-Agent": "firstep-wiki-probe"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - 探针脚本，网络失败即打印
        return f"<抓取失败：{exc}>"
    text = re.sub(r"<script.*?</script>", " ", body, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:400]


def _pdf_text(rel: str, limit: int = 1200) -> str:
    import fitz  # PyMuPDF，库内已依赖

    path = ROOT / rel
    if not path.is_file():
        return "<文件不存在>"
    doc = fitz.open(path)
    text = "".join(doc[i].get_text() for i in range(doc.page_count))
    return re.sub(r"\s+", " ", text)[:limit]


def main() -> int:
    links = index_links()
    print(f"wiki 索引链接 {len(links)} 条")
    for slug, keywords in QUERIES.items():
        print(f"=== {slug}")
        hits = [
            link
            for link in links
            if any(keyword.lower() in link.lower() for keyword in keywords)
        ]
        print(f"    wiki 索引命中：{hits if hits else '无'}")
        for keyword in keywords:
            print(f"    立创商城搜索「{keyword}」：{_lcsc_search(keyword)}")
    print("=== 本地手册原文线索")
    for rel in (
        "sources/materials/无线串口模块资料/DL-20/DL-20使用说明书.pdf",
        "sources/materials/2026_04_地猛星电赛控制题配套资料/【云台】02_DCC-100v3说明书-2026-05-24.pdf",
    ):
        print(f"--- {rel}")
        print("   " + (_pdf_text(rel) or "<无文本层>"))
    print("=== 入门教程页外部链接（led / key 板载资源口径）")
    for url in (
        "https://wiki.lckfb.com/zh-hans/dmx/beginner/led.html",
        "https://wiki.lckfb.com/zh-hans/dmx/ccs-beginner/led.html",
        "https://wiki.lckfb.com/zh-hans/dmx/beginner/key.html",
        "https://wiki.lckfb.com/zh-hans/dmx/ccs-beginner/key.html",
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/beginner/led.html",
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/beginner/key.html",
    ):
        try:
            found = _page_links(url)
        except Exception as exc:  # noqa: BLE001
            print(f"    {url} → 抓取失败：{exc}")
            continue
        print(f"    {url} → {found if found else '无站外采购链接'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
