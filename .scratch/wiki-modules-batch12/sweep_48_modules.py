# -*- coding: utf-8 -*-
"""批次 1-12 全部 48 件收尾一致性快检（提交前只读扫描）。

镜像 .scratch/wiki-modules-batch11/sweep_46_modules.py 的检查面：
ADR 0009 标记 / verified / hardware_bound / wordlist lib_modules 挂接 /
kit / source_url / 仅 mspm0 条目；依赖正检（用 delay_* 必须依赖 delay、
用 adc_get 必须依赖 adc、双平台 API 对偶枚举豁免）。
本批新增：lcd（六屏合一单模块）、tp_xpt2046（独立触摸件）；oled SPI
变体扩展既有 oled 条目（不新增 slug——oled 依赖正检照旧覆盖）。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")
from contest_generator.clex import strip_comments  # noqa: E402
MOD = Path("library/modules")
wl = json.load(open("src/contest_generator/wordlist.json", encoding="utf-8"))
libmods = set()
for g in wl:
    for s in g.get("solutions", []):
        libmods.update(s.get("lib_modules", []))

batch_slugs = [
    # 批次 1（4）
    "joystick", "hc05", "nrf24l01", "ir_remote",
    # 批次 2（4）
    "dht11", "us016", "bh1750", "ir_distance",
    # 批次 3（3）
    "max7219", "pca9685", "ir_remote_tx",
    # 批次 4（4）
    "jq8900", "syn6288", "rc522", "fingerprint",
    # 批次 5（4）
    "ads1115", "tcs34725", "mlx90614", "at24c02",
    # 批次 6（4）
    "ds18b20", "sht30", "mq2", "ttp224",
    # 批次 7（4）
    "mq135", "mq5", "sgp30", "ags10",
    # 批次 8（4）
    "flame", "soil", "human_ir", "microwave_radar",
    # 批次 9（4）
    "photoresistance", "rain", "gp2y1014au", "s12sd",
    # 批次 10（4）
    "sht20", "jy61p", "l298n", "open_mv4",
    # 批次 11（7）
    "mq3", "mq4", "mq6", "mq7", "mq8", "mq9", "ms1100",
    # 批次 12（2 新 slug——六屏合一 lcd、独立触摸 tp_xpt2046；oled SPI
    # 变体扩展既有 oled 条目——旧件（双平台/无 ADR 标记）不纳入本检查面）
    "lcd", "tp_xpt2046",
]

print("批次件数:", len(batch_slugs))
bad = 0
for slug in batch_slugs:
    m = json.load(open(MOD / slug / "manifest.json", encoding="utf-8"))
    desc = m["description"]
    mp = m["platforms"]["mspm0"]
    flags = []
    if "ADR 0009" not in desc:
        flags.append("无ADR0009标记")
    if mp.get("verified") is not True:
        flags.append("verified非true")
    if mp.get("hardware_bound") is not False:
        flags.append("hardware_bound异常")
    deps = m.get("dependencies", [])
    # 依赖正检：code 用到 delay_*/adc_get 则必须依赖 delay/adc
    joined = ""
    for f in mp.get("files", []):
        joined += Path(MOD / slug / f).read_text(encoding="utf-8", errors="replace")
    code = strip_comments(joined)
    if re.search(r"\bdelay_(us|ms|cycles)\s*\(", code) and "delay" not in deps:
        flags.append("用delay未依赖")
    if re.search(r"\badc_get\s*\(", code) and "adc" not in deps:
        flags.append("用adc_get未依赖")
    if slug not in libmods:
        flags.append("wordlist未挂接")
    if mp.get("source_url") is None:
        flags.append("缺source_url")
    if mp.get("kit") is None:
        flags.append("缺kit")
    # mspm0 平台条目禁止出现 stm32（仅 mspm0 条目，批次 1 先例）
    if "stm32" in m.get("platforms", {}):
        flags.append("混入stm32条目")
    line = f"{slug:18s} " + ("OK" if not flags else "; ".join(flags))
    print(line)
    if flags:
        bad += 1
print("异常件数:", bad)
