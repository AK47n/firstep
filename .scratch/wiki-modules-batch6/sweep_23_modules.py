# -*- coding: utf-8 -*-
"""批次 1-6 全部 23 件收尾一致性快检（提交前只读扫描）。

镜像 .scratch/wiki-modules-batch5/sweep_19_modules.py 的检查面：
ADR 0009 标记 / verified / hardware_bound / wordlist lib_modules 挂接 /
kit / source_url；依赖检查改为「除 GPIO 薄封装（ttp224）外均依赖 delay」。
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
]
# GPIO 薄封装（无延迟/无外设时序）合法的零依赖例外——正检（用 delay 才要求
# 依赖）下无需例外表，留注释说明。

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
    # 依赖表与代码一致（正检）：code 用到 delay_* 则必须依赖 delay
    uses_delay = False
    for f in mp.get("files", []):
        text = Path(MOD / slug / f).read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bdelay_(us|ms|cycles)\s*\(", strip_comments(text)):
            uses_delay = True
    if uses_delay and "delay" not in deps:
        flags.append("用delay未依赖")
    if slug not in libmods:
        flags.append("wordlist未挂接")
    if mp.get("source_url") is None:
        flags.append("缺source_url")
    if mp.get("kit") is None:
        flags.append("缺kit")
    line = f"{slug:14s} " + ("OK" if not flags else "; ".join(flags))
    print(line)
    if flags:
        bad += 1
print("异常件数:", bad)
