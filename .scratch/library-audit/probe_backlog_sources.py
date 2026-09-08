"""待补器件「可核实出处」核实脚本（工单 identity-fields/04 + 04 续）。

对 7 个 slug 逐条核对**三类**可核实出处，输出即工单 04 Comments 表格的依据：

  ① 立创 wiki 模块手册索引页（dmx 70 条 / dkx-stm32f103c8t6 77 条，
     `wiki_index_links.index_links()` 在线抓取）里有没有对应器件手册页；
  ② 库内其它可能承载同一硬件的条目（已回填的 source_url）；
  ③ 厂商官方产品页 / 明确采购页（本轮新增：`VENDOR_PAGES` 逐条 HEAD/GET 实测，
     状态码 + 页面标题即「该页确实讲这件硬件」的凭据）。

判据（工单 04 续裁决口径）：`source_url` 必须指**同一件实物**的可采购 / 官方页。
因此教程页（讲板载资源）、别的板族的同类页、不同驱动形态的页都**不算**——
本脚本把这些候选也一并实测列出，好让「为什么没填」可复现。

用法：
  $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/probe_backlog_sources.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
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

# 本轮（04 续）实测的候选出处页：URL → 说明（判定它是 / 不是「同一件实物」）。
# zigbee_link 已按此表回填双平台；其余条目保留为「候选但不算」的取证记录。
VENDOR_PAGES: dict[str, tuple[str, ...]] = {
    "zigbee_link": (
        # ✅ 已回填：厂商 Hexin 官方产品页，型号 DL-20、250m TTL 转 ZigBee、CC2530、UART 透传
        "https://www.hexin-technology.com/250m_TTL_to_ZigBee_Module-Product-565.html",
    ),
    "beep": (
        # ❌ 不算：别的板族（ColorEasyDuino）的**无源**蜂鸣器模块页——库内 beep 是
        # **有源**（低电平触发，见 beep_stm32.c 头注释），驱动形态不同即不是同一件实物
        "https://wiki.lckfb.com/zh-hans/coloreasyduino/module/control/low-passive-buzzer.html",
        # ❌ 不算：天巧星板载无源蜂鸣器教程（PWM 调音），同样是板载 + 无源
        "https://wiki.lckfb.com/zh-hans/tqx-mspm0g3519/ccs-beginner/buzzer.html",
    ),
    "led": (
        # ❌ 不算：地猛星板载 LED 教程（原理图 PA14），库内 led 默认脚 PA15（LED_BEEP 组）、
        # stm32 侧默认 PC13/14/15——讲的是板载资源，不是用户采购的那件
        "https://wiki.lckfb.com/zh-hans/dmx/beginner/led.html",
        "https://wiki.lckfb.com/zh-hans/dmx/ccs-beginner/led.html",
    ),
    "key": (
        # ❌ 不算：地猛星板载按键教程（原理图 PA18，且 PA18 是 BSL 引脚），库内 key
        # 默认 PA2（mspm0）/ PB3（stm32）——同样讲板载资源
        "https://wiki.lckfb.com/zh-hans/dmx/beginner/key.html",
        "https://wiki.lckfb.com/zh-hans/dmx/ccs-beginner/key.html",
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/beginner/key.html",
    ),
    "step_motor": (
        # ❌ 不算：别的板族（GD32E230C8T6）的**二相四线步进电机**模块页——库内实物是
        # DCC-100v3 驱动板 + 闭环步进（本仓 sources/materials 有说明书，无公开采购页）
        "https://wiki.lckfb.com/zh-hans/gd32e230c8t6/module/control/two-phase-four-wire-stepper-motor.html",
    ),
    "ir_beam": (
        # ❌ 不算：红外距离 / 循迹 / 人体红外页都不是「对射」件（探针关键词命中即这些）
        "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/Infrared-distance-sensor.html",
        "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/Infrared-tracking-sensor.html",
        "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/human-body-infrared-sensor.html",
    ),
    "led_beep": (),
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


def _probe(url: str) -> str:
    """HTTP 实测：状态码 + <title>（能打开且标题对得上 = 该页确实讲这件硬件）。"""
    try:
        with urllib.request.urlopen(  # noqa: S310
            urllib.request.Request(url, headers={"User-Agent": "firstep-wiki-probe"}),
            timeout=30,
        ) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = response.status
    except Exception as exc:  # noqa: BLE001 - 探针脚本
        return f"抓取失败：{exc}"
    title = re.search(r"<title[^>]*>(.*?)</title>", body, re.S)
    return f"{status} · {title.group(1).strip() if title else '<无标题>'}"


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
        for url in VENDOR_PAGES.get(slug, ()):
            print(f"    候选出处 {url}\n        → {_probe(url)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
