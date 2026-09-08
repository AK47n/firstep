# -*- coding: utf-8 -*-
"""批次 11 code-review 辅助：七件 manifest 结构对仗 + 代码归一化 diff（只读）。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "library" / "modules"
SLUGS = ["mq3", "mq4", "mq6", "mq7", "mq8", "mq9", "ms1100"]

print("=== manifest 结构对仗（mq2 为基准）===")
base = json.loads((MOD / "mq2" / "manifest.json").read_text(encoding="utf-8"))
print("mq2 keys:", sorted(base.keys()), "| mspm0 keys:", sorted(base["platforms"]["mspm0"].keys()))
for s in SLUGS:
    m = json.loads((MOD / s / "manifest.json").read_text(encoding="utf-8"))
    top = sorted(m.keys())
    p = m["platforms"]["mspm0"]
    pk = sorted(p.keys())
    pins = [(x["id"], x["type"], x["default"], x["required"]) for x in p["pins"]]
    print(f"{s}: top={top} deps={m['dependencies']} files={p['files']} verified={p['verified']} "
          f"hw={p['hardware_bound']} pins={pins} kit={p['kit'][:40]!r}... url={p['source_url']}")
    if top != sorted(base.keys()):
        print(f"  !! top-level keys differ: {top}")
    if pk != sorted(base["platforms"]["mspm0"].keys()):
        print(f"  !! mspm0 keys differ: {pk}")
    if m["dependencies"] != base["dependencies"]:
        print(f"  !! deps differ")
    if pins != [("MQ2_AO_CH0", "adc", "PA24", True)]:
        print(f"  !! pins differ from mq2 pattern (id tail expected _AO_CH0)")

print()
print("=== 代码归一化 diff（先差文件字节，再按换行数对比）===")
def norm(slug: str) -> str:
    return slug.replace("3", "X").replace("4", "X").replace("6", "X").replace("7", "X").replace("8", "X").replace("9", "X")

for s in SLUGS:
    for f in ("code/%s.c" % s, "code/%s.h" % s):
        txt = (MOD / s / f).read_text(encoding="utf-8")
        print(f"{s}/{f}: {len(txt)} bytes, no-{s}-token? {s.lower() in txt.lower()}")
