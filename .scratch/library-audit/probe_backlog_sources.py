"""待补器件「wiki 索引里没有手册页」的可复现核实（工单 identity-fields/04）。

对 7 个待补 slug 逐条核对：立创 wiki 两个模块手册索引页（dmx 70 条 /
dkx-stm32f103c8t6 77 条，由 wiki_index_links.py 抽取）里有没有对应器件手册页，
并列出库内其它可能承载同一硬件的条目——都没有 = 该条目的购买出处确实核不出。

用法：
  $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/probe_backlog_sources.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wiki_index_links import index_links  # noqa: E402

# 待补 slug → (中文名, 索引页里可能的页名关键词)
BACKLOG: dict[str, tuple[str, tuple[str, ...]]] = {
    "beep": ("有源蜂鸣器模块", ("buzzer", "beep", "蜂鸣")),
    "ir_beam": ("红外对射传感器", ("beam", "Infrared-beam", "对射")),
    "key": ("独立轻触按键模块", ("key", "button", "按键")),
    "led": ("LED 指示灯", ("led",)),
    "led_beep": ("LED + 蜂鸣器声光组合", ("led", "buzzer", "beep")),
    "step_motor": ("脉冲式步进电机 + 驱动板", ("step", "motor")),
    "zigbee_link": ("Zigbee DL-20 串口透传模块", ("zigbee", "dl-20", "zigbee-module")),
}


def _library_urls() -> list[str]:
    urls: list[str] = []
    for manifest in sorted(MODULES.glob("*/manifest.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for entry in (data.get("platforms") or {}).values():
            url = entry.get("source_url") or ""
            if url:
                urls.append(url)
    return sorted(set(urls))


def main() -> int:
    links = index_links()
    lib_urls = _library_urls()
    print(f"索引页链接 {len(links)} 条（dmx + dkx 两平台模块手册）；库内已有 source_url {len(lib_urls)} 条")
    for slug, (label, keywords) in BACKLOG.items():
        hits = [
            link
            for link in links
            if any(keyword.lower() in link.lower() for keyword in keywords)
        ]
        print(f"=== {slug}（{label}）")
        print(f"    wiki 模块手册索引命中：{hits if hits else '无'}")
        related = [url for url in lib_urls if slug.split("_")[0] in url]
        print(f"    库内可能同硬件条目 URL：{related if related else '无'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
