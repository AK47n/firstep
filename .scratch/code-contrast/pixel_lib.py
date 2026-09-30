"""代码配色族轮 · **读像素的公共半**（probe-02 / probe-08 两个读数脚本共用）。

## 为什么有这个文件

这一轮的读数脚本有两个都建立在"把一张 PNG 的颜色分布读出来"上：

| 脚本 | 读什么 |
|---|---|
| `probe-02-paint-order-read.py` | 代码页高亮层的字形像素（**压在字上还是垫在字下**） |
| `probe-08-disabled-state-read.py` | 禁用控件的字形像素（**灰底灰字**实没实到屏幕上） |

两份都要「整图直方图 → 主色（底）→ 字形核心」这套算法。**只留一份**（工单 03 抽出来的；
在此之前 probe-02 的读数半自己带着一份，probe-08 再抄一份就是 Duplicated Code）。

## 两条口径（别改轻）

1. **字形核心 ≠ 前几名高频色**：小字号下真核心像素数常常比抗锯齿混色少——只在前 6 高频里挑
   会挑到混色，量出来偏亮、比值偏低（probe-02 实测踩过）。所以走**全量直方图 + 像素数门槛**。
2. **主色 = 底**：取样盒里出现频率最高的那个颜色。它只有在"单一底"时才是底——掺了别的层
   （相邻行 / 叠加态 / 渐变）时读数脚本要**如实跳过比值**，不能当证据。

颜色数学（对比度公式）**不在这里**：那是 `light-contrast/probe_lib.py` 的口径单源
（与守卫腿⑧ 同源、镜像守卫钉住）。本文件只做像素统计。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import fitz


def hx(c) -> str:
    """RGB 元组 → `#rrggbb`（只取前三位，alpha 不进字符串）。"""
    return "#%02x%02x%02x" % tuple(c[:3])


def dist(a, b) -> int:
    """两色的曼哈顿距离（读像素与预测对差用）。"""
    return sum(abs(a[i] - b[i]) for i in range(3))


def histogram(path: Path) -> Counter:
    """整张图的颜色直方图（**全量**，不只前几名——字形核心常常不是最高频那几个）。"""
    pix = fitz.Pixmap(str(path))
    if pix.n > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    cnt: Counter = Counter()
    for y in range(pix.height):
        for x in range(pix.width):
            cnt[pix.pixel(x, y)[:3]] += 1
    return cnt


def dominant(cnt: Counter):
    """主色（= 取样盒里的底）与它的像素数。"""
    return cnt.most_common(1)[0]


def glyph_core(cnt: Counter):
    """字形核心 = **够多像素**的那些颜色里，离主色（底）最远的那个。

    ⚠ 只在"前 6 高频"里挑会挑到**抗锯齿混色**（probe-02 实测：小字号样本的真核心像素数
    比混色像素少，于是量出来偏亮、比值偏低）——所以这里用全量直方图 + 一个像素数门槛。
    """
    bg, _n = dominant(cnt)
    total = sum(cnt.values())
    floor = max(3, int(total * 0.005))
    cands = [c for c, n in cnt.items() if n >= floor]
    return max(cands or [bg], key=lambda c: dist(c, bg))
