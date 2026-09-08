# -*- coding: utf-8 -*-
"""从最终 wordlist 备份重新生成 state1（去掉 MQ-5/SGP30/AGS10 方案 + models 三项）。"""
import json
from pathlib import Path

w = Path(".scratch/wiki-modules-batch7/rebuild/final/wordlist.json").read_text(
    encoding="utf-8"
)
for name in (
    "MQ-5 液化气/天然气传感器",
    "SGP30 空气质量传感器（TVOC/CO2e）",
    "AGS10 有害气体传感器（TVOC）",
):
    start = w.find('      {\n        "name": "' + name + '",')
    assert start >= 0, name
    end = w.find('      {\n        "name": "', start + 1)
    assert end > start, name
    w = w[:start] + w[end:]
w = w.replace('"MQ-2", "MQ-135", "MQ-5", "SGP30", "AGS10", "TTP224"',
              '"MQ-2", "MQ-135", "TTP224"')
assert '"MQ-5' not in w and '"SGP30' not in w and '"AGS10' not in w
Path("src/contest_generator/wordlist.json").write_text(w, encoding="utf-8")
data = json.loads(w)
for g in data:
    if g.get("category") == "感知传感器":
        print([s["name"] for s in g.get("solutions", [])])
        print(g["models"])
print("wordlist state1 done")
