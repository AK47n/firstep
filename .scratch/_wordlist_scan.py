# -*- coding: utf-8 -*-
"""临时探针：打印 wordlist.json 分类、方案名与 lib_modules 挂接（供批次 1 补录决策）。"""
import io
import json

d = json.load(io.open("src/contest_generator/wordlist.json", encoding="utf-8"))
out = []
for i, g in enumerate(d):
    out.append(f"[{i}] category={g['category']} models={g.get('models')}")
    for j, s in enumerate(g.get("solutions", [])):
        out.append(f"    ({i}.{j}) name={s['name']} lib_modules={s.get('lib_modules')}")
io.open(".scratch/_wordlist_scan.txt", "w", encoding="utf-8").write("\n".join(out))
print("ok")
