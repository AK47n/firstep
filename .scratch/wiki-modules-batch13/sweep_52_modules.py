# -*- coding: utf-8 -*-
"""批次 1-13 全部 52 件 mspm0 条目收尾一致性快检（提交前只读扫描）。

口径（2026-09 修订）：本脚本只守 **mspm0 线**（wiki-modules-batch1-13 的
mspm0 平台条目）字段不变量；**同 slug 是否已有 stm32 条目属 stm32 线
（wiki-stm32-batch*）的管理面，由 .scratch/wiki-stm32-batch11/
sweep_stm32_full.py 核对，本脚本不再视为异常**（2026-09 stm32 线开建前，
本脚本曾断言 mspm0 条目禁止混入 stm32——该前置已被设计推翻，故删除该断言；
否则 50/52 假 FAIL，脚本失去门禁意义）。

检查面（镜像 .scratch/wiki-modules-batch12/sweep_48_modules.py）：
- description 含 ADR 0009 标记（纯驱动切片判据）
- mspm0 条目 verified=True / hardware_bound=False / kit / source_url 齐备
- 依赖正检：code 用到 delay_*/adc_get 必须依赖 delay/adc
- wordlist lib_modules 挂接
- 批次溯源：notes 含批次标记（info 输出，不作异常）
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

# 批次 1-13 入册 slug（52 件，按批次注释）
batch_slugs = [
    # 批次 1（4 件）
    "joystick", "hc05", "nrf24l01", "ir_remote",
    # 批次 2（4 件）
    "dht11", "us016", "bh1750", "ir_distance",
    # 批次 3（3 件）
    "max7219", "pca9685", "ir_remote_tx",
    # 批次 4（4 件）
    "jq8900", "syn6288", "rc522", "fingerprint",
    # 批次 5（4 件）
    "ads1115", "tcs34725", "mlx90614", "at24c02",
    # 批次 6（4 件）
    "ds18b20", "sht30", "mq2", "ttp224",
    # 批次 7（4 件）
    "mq135", "mq5", "sgp30", "ags10",
    # 批次 8（4 件）
    "flame", "soil", "human_ir", "microwave_radar",
    # 批次 9（4 件）
    "photoresistance", "rain", "gp2y1014au", "s12sd",
    # 批次 10（4 件）
    "sht20", "jy61p", "l298n", "open_mv4",
    # 批次 11（7 件）
    "mq3", "mq4", "mq6", "mq7", "mq8", "mq9", "ms1100",
    # 批次 12（2 件新 slug + oled SPI 变体扩展既有条目）
    "lcd", "tp_xpt2046",
    # 批次 13（4 件收官小批：relay 执行机构 / as32 无线数传 / bmp180+ms5611 气压互替件）
    "relay", "as32", "bmp180", "ms5611",
]

print("批次件数:", len(batch_slugs))
seen = set(batch_slugs)
dup = sorted(s for s in seen if batch_slugs.count(s) > 1)
if dup:
    print("FAIL: batch_slugs 重复:", dup)
    sys.exit(1)

bad = 0
has_stm32 = 0
no_batch_mark = []
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
    if not mp.get("kit"):
        flags.append("缺kit")
    if not mp.get("source_url"):
        flags.append("缺source_url")
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
    # stm32 条目现状只作统计（管理面归 stm32 线 sweep），不作异常
    if "stm32" in m.get("platforms", {}):
        has_stm32 += 1
    if "wiki-modules-batch" not in json.dumps(m, ensure_ascii=False):
        no_batch_mark.append(slug)
    line = f"{slug:18s} " + ("OK" if not flags else "; ".join(flags))
    print(line)
    if flags:
        bad += 1

print("异常件数:", bad)
print(f"已有 stm32 条目（stm32 线管理，非本脚本异常）: {has_stm32}/{len(batch_slugs)}")
if no_batch_mark:
    print("无批次溯源标记（应对照工单补 notes）:", no_batch_mark)
if bad:
    sys.exit(1)
print("SWEEP OK（52 件 mspm0 条目字段不变量全部通过；入口 .scratch/"
      "wiki-modules-batch13/sweep_52_modules.py）")
