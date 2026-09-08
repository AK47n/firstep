# -*- coding: utf-8 -*-
"""地阔星 wiki 页 ↔ 库内模块清单映射（spec 前置一次性盘点）。

输出：
- .scratch/materials-wiki/dkx-inventory.tsv：逐模块映射（lib/stm/stm_files/msp/wiki/dkx）
- 控制台汇总（各分类计数与清单）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"
DKX_URLS = Path(__file__).parent / "dkx-module-urls.txt"
OUT_TSV = Path(__file__).parent / "dkx-inventory.tsv"

dkx_slugs = set()
for line in DKX_URLS.read_text(encoding="utf-8-sig").splitlines():
    line = line.strip()
    if not line:
        continue
    parts = line.strip("/").split("/")
    slug = re.sub(r"\.html$", "", parts[-1])
    dkx_slugs.add(slug)

rows = []
for d in sorted(MODULES.iterdir()):
    if not d.is_dir():
        continue
    mp = d / "manifest.json"
    if not mp.exists():
        continue
    j = json.loads(mp.read_text(encoding="utf-8"))
    plat = j.get("platforms", {})
    stm = plat.get("stm32")
    msp = plat.get("mspm0")
    src = ""
    if msp and msp.get("source_url"):
        src = msp["source_url"]
    elif stm and stm.get("source_url"):
        src = stm["source_url"]
    wiki = ""
    m2 = re.search(r"wiki\.lckfb\.com.*?/module/([^/]+)/([^/]+)\.html", src)
    if m2:
        wiki = m2.group(2)
    dkx = wiki in dkx_slugs
    rows.append({
        "lib": d.name,
        "stm": bool(stm),
        "stm_files": ",".join((stm or {}).get("files", []) or []),
        "msp": bool(msp),
        "wiki": wiki,
        "dkx": dkx,
    })

lines = ["lib\tstm\tstm_files\tmsp\twiki\tdkx"]
for r in rows:
    lines.append(f"{r['lib']}\t{int(r['stm'])}\t{r['stm_files']}\t{int(r['msp'])}\t{r['wiki']}\t{int(r['dkx'])}")
OUT_TSV.write_text("\n".join(lines), encoding="utf-8")

def emit(s: str) -> None:
    print(s)
    sys.stdout.flush()

emit(f"库模块总数 {len(rows)}；有 stm32 条目 {sum(1 for r in rows if r['stm'])}；无 {sum(1 for r in rows if not r['stm'])}")
# 关键映射：无 stm32 条目 + wiki 来源 + 地阔星有对应页 = 本批待新增主体
cand = [r for r in rows if not r["stm"] and r["wiki"] and r["dkx"]]
emit(f"候选（无 stm32 + wiki 源 + 地阔星有页）{len(cand)} 件：")
emit(" ".join(r["lib"] for r in cand))
skip = [r for r in rows if not r["stm"] and r["wiki"] and not r["dkx"]]
emit(f"无 stm32 + wiki 源但地阔星无对应页 {len(skip)} 件：{', '.join(r['lib'] + '(' + r['wiki'] + ')' for r in skip)}")
new = sorted(set(dkx_slugs))
# 地阔星页面里没有任何库模块引用(按 dmx source_url 匹配) = 新模块或库内已有但无 wiki 来源
known = {r["wiki"] for r in rows if r["wiki"]}
unreferenced = sorted(s for s in dkx_slugs if s not in known)
emit(f"地阔星页面未被任何库模块 source_url 引用 {len(unreferenced)} 件：")
emit(" ".join(unreferenced))
