# -*- coding: utf-8 -*-
"""wordlist 单独回退到 state1（去掉 MQ-5/SGP30/AGS10 方案 + models 三项）。"""
import json

w = open("src/contest_generator/wordlist.json", encoding="utf-8").read()
for name in (
    "MQ-5 液化气/天然气传感器",
    "SGP30 空气质量传感器（TVOC/CO2e）",
    "AGS10 有害气体传感器（TVOC）",
):
    start = w.find('      {\n        "name": "' + name + '",')
    end = w.find('      {\n        "name": "', start + 1)
    if end < 0:
        end = w.find('    }\n  }\n]', start)
    assert start >= 0 and end > start, (name, start, end)
    w = w[:start] + w[end:]
w = w.replace('"MQ-2", "MQ-135", "MQ-5", "SGP30", "AGS10", "TTP224"',
              '"MQ-2", "MQ-135", "TTP224"')
w = w.replace('"MQ-2", "MQ-135", "SGP30", "AGS10", "TTP224"',
              '"MQ-2", "MQ-135", "TTP224"')
open("src/contest_generator/wordlist.json", "w", encoding="utf-8").write(w)
data = json.loads(w)
for g in data:
    if g.get("category") == "感知传感器":
        print([s["name"] for s in g.get("solutions", [])])
        print(g["models"])
print("wordlist state1 done")
