# -*- coding: utf-8 -*-
"""临时诊断：**推荐链路**在真实赛题上会不会同时推两件 mspm0 引脚符号撞名的模块？

为什么要量这个：工单 11 的缺陷（`SCL`/`SDA` 等 14 组重名）只在"同趟选中两件撞名的
实例"时炸。20 道真题里没有一道点名 I2C 器件（只说"显示屏""姿态"），所以"用户会不会
真的同时选两件"不能靠猜——推荐链路是确定性的本地计算，直接算一遍：

* 预筛（`preselect_module_summaries`）= 题面激活的词项命中模块匹配面 → 排序截断，
  这是模型**看得见**的那份候选清单；
* 判据：预筛清单里是否同时出现同一重名组里的两个 slug（如 oled + jy61p、
  lcd + sht20、rc522 + hw711 …）。

注意：预筛是"模型看得见什么"，不是"最终选了谁"——所以下面给的是**上界**
（候选清单里同时可见 = 模型完全可能两件都推）。读数里两条都记：可见对数 + 与
题面词项直接相关的对数（后者更接近真实推荐）。
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.selection import preselect_module_summaries  # noqa: E402

MODULES = REPO / "library" / "modules"
TOPICS = REPO / "library" / "topics"
MASTER = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"

# ① 从母版扫出重名组（判据：.$name 的路径含 .associatedPins[，同一取值出现在
#    两个以上实例）+ 实例名 → slug（用 INSTANCE_CONSUMERS 那张单源表）
from contest_generator.syscfg_instances import INSTANCE_CONSUMERS  # noqa: E402

slug_of: dict[str, str] = {}
for instance, slugs in INSTANCE_CONSUMERS.items():
    for slug in slugs:
        slug_of.setdefault(instance, slug)

text = MASTER.read_text(encoding="utf-8")
raw: dict[str, set[str]] = {}
for line in text.splitlines():
    s = line.strip()
    if not s.endswith(";") or ".$name" not in s or "=" not in s:
        continue
    path, value = s[:-1].split("=", 1)
    if ".associatedPins[" not in path:
        continue
    instance = path.split(".associatedPins")[0]
    slug = slug_of.get(instance)
    if slug:
        raw.setdefault(value.strip().strip('"'), set()).add(slug)
groups = {name: sorted(slugs) for name, slugs in raw.items() if len(slugs) > 1}
print(f"重名组（映射到库内 slug 后）：{len(groups)} 组")
for name, slugs in sorted(groups.items()):
    print(f"  {name:5s} -> {', '.join(slugs)}")

# ② 每道真题跑一次预筛，看清单里有没有成对的
summaries = build_manifest_summaries(list_modules(MODULES))
print(f"\n模块摘要：{len(summaries)} 条\n")

total_pairs = 0
print("按题看**前排**（预筛是排序表，模型先看排前面的）：\n")
for entry in sorted(TOPICS.iterdir()):
    topic_file = entry / "topic.md"
    if not topic_file.is_file():
        continue
    topic = topic_file.read_text(encoding="utf-8")
    result = preselect_module_summaries(summaries, topic)
    ranked = [s.slug for s in result.summaries]
    for top_n in (10, 20):
        visible = set(ranked[:top_n])
        pairs: list[str] = []
        for name, slugs in groups.items():
            present = [s for s in slugs if s in visible]
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    pairs.append(f"{present[i]}+{present[j]}")
        if top_n == 10:
            head = "、".join(ranked[:10])
            print(f"{entry.name}（预筛 {len(ranked)} 条）前 10：{head}")
            print(f"    前 10 里撞名对：{len(pairs)}" + (f" → {'、'.join(pairs)}" if pairs else ""))
            total_pairs += len(pairs)
print(f"\n合计（前 10 内）：{total_pairs} 对")
