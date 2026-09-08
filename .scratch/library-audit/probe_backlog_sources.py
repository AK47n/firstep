"""待补器件「可核实出处」核实脚本（工单 identity-fields/04 + 04 续 + 05 续）。

对 6 个待补 slug 逐条核对**三类**可核实出处，输出即工单 04 Comments 表格的依据：

  ① 立创 wiki 模块手册索引页（dmx 70 条 / dkx-stm32f103c8t6 77 条，
     `wiki_index_links.index_links()` 在线抓取）里有没有对应器件手册页；
     `--all-boards` 再扩面到 8 个板族（dzx / tmx / tqx / gd32e230c8t6 /
     tjx-tms320f28p550 / coloreasyduino），证明「没有」是全站结论；
  ② 库内其它可能承载同一硬件的条目（已回填的 source_url）；
  ③ 厂商官方产品页 / 明确采购页 / 商城模块页（`VENDOR_PAGES` 逐条 HTTP 实测，
     状态码 + 页面标题即「该页确实讲这件硬件」的凭据）。

判据（工单 04 续裁决一）：`source_url` 必须指**同一件实物**的可采购 / 官方页。
因此教程页（讲板载资源）、别的板族的同类页、不同驱动形态的页、元件级商品页、
B2B 批发页都**不算**——本脚本把这些候选也一并实测列出，好让「为什么没填」可复现。

用法：
  $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/probe_backlog_sources.py
  $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/probe_backlog_sources.py --all-boards
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

from wiki_index_links import all_board_links, index_links  # noqa: E402

# 全站扩面扫描关键词（05 续）：待补器件在别板模块手册里的任何可能页名。
_ALL_KEYWORDS = (
    "buzzer", "beep", "stepper", "step-motor", "beam", "photoelectric",
    "led", "key", "button",
)

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

# 实测的候选出处页：URL → 说明（判定它是 / 不是「同一件实物」）。
# zigbee_link 已按此表回填双平台；其余条目保留为「候选但不算」的取证记录。
# 「04 续」= 第二轮（wiki 索引 + 三页候选）；「05 续」= 第三轮（商城模块页 / 元件页 /
# 厂商页扩面：立创商城商品页、1688、lckfb 项目页、oshwhub 开源板）。
VENDOR_PAGES: dict[str, tuple[str, ...]] = {
    "zigbee_link": (
        # ✅ 已回填：厂商 Hexin 官方产品页，型号 DL-20、250m TTL 转 ZigBee、CC2530、UART 透传
        "https://www.hexin-technology.com/250m_TTL_to_ZigBee_Module-Product-565.html",
    ),
    "beep": (
        # ❌ 不算（04 续）：别的板族（ColorEasyDuino）的**无源**蜂鸣器模块页——库内 beep 是
        # **有源**（低电平触发，见 beep_stm32.c 头注释），驱动形态不同即不是同一件实物
        "https://wiki.lckfb.com/zh-hans/coloreasyduino/module/control/low-passive-buzzer.html",
        # ❌ 不算（04 续）：天巧星板载无源蜂鸣器教程（PWM 调音），同样是板载 + 无源
        "https://wiki.lckfb.com/zh-hans/tqx-mspm0g3519/ccs-beginner/buzzer.html",
        # ⚠️ 05 续最接近的候选：立创商城「有源电磁式蜂鸣器模块」JX020101（技小新）
        # ——有源 + 模块形态对得上，但**触发极性相反**（页面：控制信号需为高电平，
        # 低电平或悬空不发声；库内 beep_stm32.c 是低电平响），且商品已下架
        # （productCycle=sold_out）。极性算不算「同一件实物」见工单 04 Comments 口径问题
        "https://item.szlcsc.com/product/jpg_142986.html",
        # ❌ 不算（05 续）：HYT-1203 是**元件级**有源蜂鸣器（DIP，蜂鸣片本体），
        # 库内驱动的是 3 线制模块（VCC/GND/OUT + 驱动电路）
        "https://item.szlcsc.com/product/jpg_8653402.html",
        # ❌ 不算（05 续）：1688 电子积木有源蜂鸣器模块「低电平触发」——极性对得上，
        # 但 1688 是 B2B 批发页（工单 04 裁决一第 3 条：B2B 批发页不算）
        "https://detail.1688.com/offer/705821334436.html",
    ),
    "led": (
        # ❌ 不算（04 续）：地猛星板载 LED 教程（原理图 PA14），库内 led 默认脚 PA15（LED_BEEP 组）、
        # stm32 侧默认 PC13/14/15——讲的是板载资源，不是用户采购的那件
        "https://wiki.lckfb.com/zh-hans/dmx/beginner/led.html",
        "https://wiki.lckfb.com/zh-hans/dmx/ccs-beginner/led.html",
        # ⚠️ 05 续最接近的候选：立创商城 TDSEMIC-479「3 色 LED 模块 KY-016」——3 通道
        # 单色灯 + 模块形态与库内 led 通道表（LED_RED/YELLOW/GREEN）对得上，但页面是
        # 发光二极管/LED 目录下的**元件级**商品（共阳 RGB 模块，非 3 路独立 GPIO 拉电流）
        "https://item.szlcsc.com/55308948.html",
    ),
    "key": (
        # ❌ 不算（04 续）：地猛星板载按键教程（原理图 PA18，且 PA18 是 BSL 引脚），库内 key
        # 默认 PA2（mspm0）/ PB3（stm32）——同样讲板载资源
        "https://wiki.lckfb.com/zh-hans/dmx/beginner/key.html",
        "https://wiki.lckfb.com/zh-hans/dmx/ccs-beginner/key.html",
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/beginner/key.html",
        # ❌ 不算（05 续）：HYT-1203 轻触开关是**元件级**（DIP 开关本体），
        # 库内 key 是「独立轻触按键模块（带上拉）」——带上拉电阻的模块
        "https://item.szlcsc.com/product/jpg_8653402.html",
    ),
    "step_motor": (
        # ❌ 不算（04 续）：别的板族（GD32E230C8T6）的**二相四线步进电机**模块页——库内实物是
        # DCC-100v3 驱动板 + 闭环步进（本仓 sources/materials 有说明书，无公开采购页）
        "https://wiki.lckfb.com/zh-hans/gd32e230c8t6/module/control/two-phase-four-wire-stepper-motor.html",
        # ❌ 不算（05 续）：DCC 厂商域名（苏州兰旺克电气设备有限公司）能打开，但站点只有
        # 公司介绍、无 DCC-100/101 产品页；汇电籽（HDZ）域名不存在；立创商城检索
        # 走 web 搜索未命中 DCC-100v3 商品页（站内搜索接口 403/JS 挑战，无法脚本化）
        "https://www.dccmotor.com/",
    ),
    "ir_beam": (
        # ❌ 不算（04 续）：红外距离 / 循迹 / 人体红外页都不是「对射」件（探针关键词命中即这些）
        "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/Infrared-distance-sensor.html",
        "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/Infrared-tracking-sensor.html",
        "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/human-body-infrared-sensor.html",
        # ❌ 不算（05 续）：XL-ITR20403 / ZGY8102(ITR) 是**元件级**槽型对射光电开关
        # （4 脚：发光管 + 光敏管裸出，需外部电路），库内 ir_beam 是 3 线制
        # VCC/GND/OUT 数字输出模块
        "https://item.szlcsc.com/8657534.html",
        "https://item.szlcsc.com/265239.html",
        # ❌ 不算（05 续）：欧姆龙 E3Z-LT61 是工业对射光电开关（¥1319，NPN/PNP 输出），
        # 不是电赛用 3 线制小模块
        "https://item.szlcsc.com/2860013.html",
    ),
    "led_beep": (
        # ❌ 不算（04 续）：组合件 = led + beep，两者都核不出，组合件更无独立页；
        # 05 续复核商城/开源板仍无「LED + 蜂鸣器」组合模块商品页
        "https://oshwhub.com/xiiaao/project_paeqkkqu",
    ),
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


def scan_all_boards() -> int:
    """全站扩面扫描：各板模块手册索引页 + 关键词命中（证明「没有」是全站结论）。"""
    for board, links in all_board_links().items():
        hits = sorted(
            link
            for link in links
            if any(k in link.lower() for k in _ALL_KEYWORDS)
        )
        print(f"=== {board}（模块手册索引 {len(links)} 条）")
        for hit in hits or ("无关键词命中",):
            print("    " + hit)
    return 0


if __name__ == "__main__":
    sys.exit(scan_all_boards() if "--all-boards" in sys.argv else main())
