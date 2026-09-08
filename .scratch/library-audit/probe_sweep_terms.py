"""临时探针：器件类别词项在**真实参考库**里的承载（工单 preselect-visibility/05 整改）。

走生产数据与生产判据：`list_references` 读库 + `_entry_score` 算命中，不自写
token 拆分、不硬编码候选标题（原版试算草稿标题，与入库结果脱节）。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    MODULE_PERIPHERAL_TERMS,
    PERIPHERAL_TERMS,
    _entry_score,
    _synonym_group,
    list_references,
)

# 工单 05 新增的器件类别词项（与 PERIPHERAL_TERMS 的注释段同源）
NEW_TERMS = (
    "气压", "光照", "颜色", "气体", "测距", "称重", "姿态", "指纹", "语音",
    "触摸", "摇杆", "彩屏", "灯带", "无线数传", "lora", "温度",
    "存储", "编码", "人体感应", "雷达", "雨滴", "土壤湿度",
)

entries = list_references(ROOT / "library" / "references")
print(f"参考条目 {len(entries)} 条；器件类别词项 {len(NEW_TERMS)} 个\n")

print("=== 每个新词项在真实库标题里的承载 ===")
dead_terms: list[str] = []
for term in NEW_TERMS:
    if term not in PERIPHERAL_TERMS:
        print(f"  {term:<8} 不在 PERIPHERAL_TERMS（词表未登记）")
        continue
    activated = frozenset(_synonym_group(term)[:1])
    hits = [e.title for e in entries if _entry_score(e, activated) > 0]
    if hits:
        print(f"  {term:<8} {len(hits):>2} 条承载：{hits[0][:40]}")
    else:
        dead_terms.append(term)
        print(f"  {term:<8} 0 命中（词项无承载条目）")
if dead_terms:
    print(f"\n[警告] 无承载词项：{'、'.join(dead_terms)}")
else:
    print("\n全部词项都有承载条目。")

print("\n=== 每个映射模块至少一个词项命中（按模块算，走生产 _entry_score）===")
dead_modules: list[str] = []
for slug, terms in sorted(MODULE_PERIPHERAL_TERMS.items()):
    activated = frozenset(_synonym_group(term)[0] for term in terms)
    if any(_entry_score(entry, activated) > 0 for entry in entries):
        continue
    dead_modules.append(f"{slug}（{'、'.join(terms)}）")
print("死映射：" + ("、".join(dead_modules) if dead_modules else "无"))
