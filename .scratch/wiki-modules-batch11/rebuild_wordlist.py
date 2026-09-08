# -*- coding: utf-8 -*-
"""wordlist.json 最小 diff 重建：还原紧凑格式（HEAD~ 形态）+ 语义改动。"""
import json
from pathlib import Path

ORIG = Path(".scratch/wiki-modules-batch11/_wl_orig.json")
DEST = Path("src/contest_generator/wordlist.json")
BLOCK = Path(".scratch/wiki-modules-batch11/_wl_block.json")

t = ORIG.read_text(encoding="utf-8")

# 1) models 行：MQ-3/4/6/7/8/9、MS1100 插到 MQ-5 之后
old = '"MQ-135", "MQ-5", "SGP30"'
assert old in t
t = t.replace(old, '"MQ-135", "MQ-5", "MQ-3", "MQ-4", "MQ-6", "MQ-7", "MQ-8", "MQ-9", "MS1100", "SGP30"', 1)

# 2) 7 个方案插在 MQ-5 条目之后
anchor = '"lib_modules": ["mq5"]\n      },'
assert anchor in t
block = BLOCK.read_text(encoding="utf-8")
t = t.replace(anchor, anchor + "\n" + block, 1)

DEST.write_text(t, encoding="utf-8")
d = json.load(open(DEST, encoding="utf-8"))
print("OK groups:", len(d))
print("感知传感器 solutions:", sum(len(g.get("solutions", [])) for g in d if g.get("category") == "感知传感器"))
