# -*- coding: utf-8 -*-
"""批次 1-5 全部 19 件收尾一致性快检（提交前只读扫描）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
MOD = Path("library/modules")
wl = json.load(open("src/contest_generator/wordlist.json", encoding="utf-8"))
libmods = set()
for g in wl:
    for s in g.get("solutions", []):
        libmods.update(s.get("lib_modules", []))

batch_slugs = [
    "joystick", "hc05", "nrf24l01", "ir_remote", "dht11", "us016", "bh1750",
    "ir_distance", "max7219", "pca9685", "ir_remote_tx", "jq8900", "syn6288",
    "rc522", "fingerprint", "ads1115", "tcs34725", "mlx90614", "at24c02",
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
    if "delay" not in m["dependencies"]:
        flags.append("未依赖delay")
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
