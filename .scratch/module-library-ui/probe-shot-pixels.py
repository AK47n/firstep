r"""像素级核对 module-library-ui/01 的存档截图（第十四轮，配合视觉通道目视）。

目的：视觉模型把「内嵌母版」标签读作「几乎没底色 / 裸文字」，需要判定这是
①「`.badge.neutral` 的极浅底在图上确实存在、只是弱」还是 ②「底根本没画上（回归）」。
同时复核工单里另几条纯视觉判据在**产物本身**上是否成立：

- 无斑马纹（相邻数据行带底色一致）
- 表头底纹存在且与数据行不同
- 红色只出现在删除钮（红字簇计数 = 行数）
- 标题 h2 未被吸顶栏遮挡（标题像素带与其上方栏带不重叠）

只读：不写库、不改产品码，输出到 stdout。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch\module-library-ui\probe-shot-pixels.py [截图名]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
NAME = sys.argv[1] if len(sys.argv) > 1 else "01-table-shot-final.png"
img = Image.open(HERE / NAME).convert("RGB")
W, H = img.size
px = img.load()
print(f"== {NAME} {W}x{H} ==")


def band(y: int, x0: int, x1: int) -> tuple[int, int, int]:
    """某一行在 x0..x1 的底色众数（避开文字/徽章：取该行出现最多的颜色）。"""
    c = Counter(px[x, y] for x in range(x0, x1))
    return c.most_common(1)[0][0]


# ---- 1) 竖直扫描：找水平色带（表头 / 数据行 / 卡片 / 页面底） ----
print("\n-- 竖直色带（x=W//2 每 4px 采样，仅打印变化点）--")
prev = None
changes = []
for y in range(0, H, 2):
    c = px[W // 2, y]
    if prev is None or max(abs(a - b) for a, b in zip(c, prev)) > 3:
        changes.append((y, c))
        prev = c
for y, c in changes[:40]:
    print(f"   y={y:4d}  {c}")
print(f"   （共 {len(changes)} 处变化）")

# ---- 2) 斑马纹：表格数据区的相邻行带底色 ----
# 表头以下、表格左边界右侧的纯底色竖条（x 取表格最左列左侧留白）
print("\n-- 斑马纹核对（x 在表格左内边距带内逐行取底色，看相邻行是否交替）--")
strip_x0, strip_x1 = 60, 110
rows = [(y, band(y, strip_x0, strip_x1)) for y in range(0, H)]
runs = []
for y, c in rows:
    if runs and runs[-1][1] == c:
        runs[-1][2] = y
    else:
        runs.append([y, c, y])
runs = [r for r in runs if r[2] - r[0] >= 12]
print(f"   ≥12px 的同色竖带：{len(runs)} 段")
for y0, c, y1 in runs[:20]:
    print(f"   y {y0:4d}-{y1:4d}（高 {y1 - y0 + 1:3d}）  rgb{c}")
bg_counter = Counter(c for _, c, _ in runs)
print(f"   出现最多的带底色：{bg_counter.most_common(3)}")

# ---- 3) 红色像素（删除钮） ----
print("\n-- 红色像素簇（删除钮；每行一簇）--")
red = [(x, y) for y in range(0, H, 2) for x in range(0, W, 2)
       if px[x, y][0] > 140 and px[x, y][1] < 110 and px[x, y][2] < 110]
print(f"   红色采样点数：{len(red)}")
if red:
    ys = sorted({y for _, y in red})
    clusters = []
    for y in ys:
        if clusters and y - clusters[-1][-1] <= 6:
            clusters[-1].append(y)
        else:
            clusters.append([y])
    print(f"   按 y 聚成 {len(clusters)} 簇，各簇 y 范围 / x 范围：")
    for cl in clusters:
        xs = [x for x, y in red if cl[0] <= y <= cl[-1]]
        print(f"     y {cl[0]:4d}-{cl[-1]:4d}   x {min(xs):4d}-{max(xs):4d}")

# ---- 4) 中性徽章底：找「比行底略亮」的小块（.badge.neutral 的 rgba(139,148,158,.15)） ----
print("\n-- 中性底小块（行底只亮一点点的圆角块）--")
common = [c for c, _ in Counter(px[x, y] for y in range(0, H, 3) for x in range(0, W, 3)).most_common(6)]
print(f"   全图最常见的 6 种颜色：{common}")
row_bg = bg_counter.most_common(1)[0][0]
cand = Counter()
for y in range(0, H):
    for x in range(0, W):
        c = px[x, y]
        d = sum(c) - sum(row_bg)
        if 6 <= d <= 60 and max(c) - min(c) < 14:      # 略亮且近似中性
            cand[(x // 20, y // 12)] += 1
blocks = [(k, v) for k, v in cand.items() if v > 60]
print(f"   行底 {row_bg} 之上「略亮的中性块」命中网格数：{len(blocks)}")
for (bx, by), v in sorted(blocks, key=lambda kv: -kv[1])[:12]:
    print(f"     ~x {bx * 20}-{bx * 20 + 19}  y {by * 12}-{by * 12 + 11}  ({v} 像素)")
if blocks:
    bx, by = max(blocks, key=lambda kv: kv[1])[0]
    x, y = bx * 20 + 10, by * 12 + 6
    print(f"   样本点 ({x},{y}) = {px[x, y]}   行底 = {row_bg}   差 = {tuple(a - b for a, b in zip(px[x, y], row_bg))}")
