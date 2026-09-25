# -*- coding: utf-8 -*-
"""把**共享候选池**补进每一条已声明 `console` 的配方（工单 07 落地时发现，见工单「整改」）。

⚠ **这不是日常工具，别顺手跑**：它会**就地重写**出货用的 `library/hwcheck_recipes.json`。
它已经跑过一次（批次 E 落地时），此后正常情况下**只读、不改**。什么时候才需要再跑：
决定要改共享池本身（换字符 / 加字符）时——那时的顺序是"改这里的 `POOL` → 重跑本脚本
→ 重跑 `probe-console-combos.py`（`|S| <= 6` 全子集必须零撞车）→ 重跑两平台编译矩阵"。
幂等：重复跑不会重复追加（已在池里的字符不会再加）。

背景（实测量具 = `.scratch/hwcheck-specialize/probe-console-combos.py`）：
`|S| <= 6`（学生真会用的规模）**全子集穷举**在批次 E 落地后出现了 3 组撞车——全部不是
本批四件的首选被抢，而是**旧件的候选太浅**被本批挤干：

    ads1115、at24c02、bmp180、pca9685、sgp30、sht30
      → `sht30` 声明 `e`（首选，被 `at24c02` 拿走）、`n`（被 `pca9685` 拿走）、
        `z`（被 `sgp30` 拿走）⇒ 分不出字符，构建期 400。

这正是交接区「写配方三条新增口径」①的同一类问题（批次 D 踩过 `at24c02` 候选 `e` 撞
`sht30` 首选）。根因不是哪一件写错了，而是**候选池整体太浅**：专精件一多，
"候选都是别人的首选"必然发生。修法 = 给每条配方补一个**共享后备池**：

    n z i 0 1 2 3

顺序的理由（实测见工单 `07-落地记录.md` §3）：`n`/`z` 是所有件都想用的公共后备，
放最前；`i` 是批次 F 的 `joystick` 的首选，放它后面；数字尾巴是最后兜底
（`at24c02` / `sgp30` / `mlx90614` 已在用这套写法）。
⚠ **每条配方的候选顺序 = 它原有的候选（保序）+ 池子里还没出现的字符**——
所以各条的实际列表不完全一样（如 `ads1115` 是 `n z c i 0 1 2 3`、
`mlx90614` 是 `n z 0 1 i 2 3`）。**已有的候选一个不删、顺序不动**是老行为逐字不变的保证。

**纯追加**：已有的候选一个不删、顺序不动（老行为的让位顺序逐字不变），
只把池子里还没有的字符补到尾部。两平台写同一份声明（与既有配方一致）。

用法：`py -3 .scratch/hwcheck-specialize/_topup_console_pool.py`
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"
POOL = ("n", "z", "i", "0", "1", "2", "3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

original = RECIPES.read_bytes()
text = original.decode("utf-8")
document = json.loads(text)

touched: list[str] = []
for slug, entry in document.items():
    if not isinstance(entry, dict):
        continue
    for platform, section in entry.items():
        console = section.get("console")
        if console is None:
            continue
        if console.get("candidates") is None:
            console["candidates"] = []
        for char in POOL:
            if char not in console["candidates"]:
                console["candidates"].append(char)
        touched.append(f"{slug}×{platform}")

newline = "\r\n" if "\r\n" in text else "\n"
body = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline) + newline
RECIPES.write_bytes(body.encode("utf-8"))
print(f"补了 {len(touched)} 格：{'、'.join(touched)}")
