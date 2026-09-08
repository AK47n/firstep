"""候选 wiki 页外部采购链接核实（工单 identity-fields/04 续）。

对每个候选页抓正文，抽取站外采购链接（淘宝 / 天猫 / 立创商城 / 京东）与含
「采购 / 购买 / 链接」的正文片段——用来判定某页能否作为 source_url 出处。

用法：
  $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/probe_candidate_pages.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wiki_index_links import fetch  # noqa: E402

CANDIDATES = (
    "https://wiki.lckfb.com/zh-hans/fdb/micropython/gpio-basic/buzzer-control.html",
    "https://wiki.lckfb.com/zh-hans/coloreasyduino/module/control/low-passive-buzzer.html",
    "https://wiki.lckfb.com/zh-hans/gd32e230c8t6/module/control/two-phase-four-wire-stepper-motor.html",
    "https://wiki.lckfb.com/zh-hans/dmx/beginner/led.html",
    "https://wiki.lckfb.com/zh-hans/dmx/beginner/key.html",
    "https://wiki.lckfb.com/zh-hans/dmx/module/control/ws2812-color-rgb-led.html",
    "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/Infrared-tracking-sensor.html",
    "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/Infrared-distance-sensor.html",
    "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/human-body-infrared-sensor.html",
)

EXT_HINTS = ("taobao", "tmall", "szlcsc", "item.htm", "detail.", "jd.com")
URL_RE = re.compile(r"https?://[^\s\"'<>\\]+")
TEXT_RE = re.compile(r"\s+")


def _text(html: str) -> str:
    body = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return TEXT_RE.sub(" ", body)


def main() -> int:
    for url in CANDIDATES:
        try:
            html = fetch(url)
        except Exception as exc:  # noqa: BLE001 - 探针
            print(f"=== {url}\n    抓取失败：{exc}")
            continue
        ext = sorted({u for u in URL_RE.findall(html) if any(h in u for h in EXT_HINTS)})
        text = _text(html)
        print(f"=== {url}")
        print(f"    外链：{ext if ext else '无'}")
        for kw in ("采购", "购买", "购买链接", "淘宝", "商城", "链接"):
            for m in re.finditer(kw, text):
                snippet = text[max(0, m.start() - 60) : m.start() + 120]
                print(f"    [{kw}] …{snippet}…")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
