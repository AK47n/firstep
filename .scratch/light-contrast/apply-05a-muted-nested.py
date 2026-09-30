"""浅色调色板轮 · 施工脚本（05 单）：把浅色 `--muted` 压到"嵌套合成底"上也过线。

## 来源（05 单的**渲染面全站扫描**逮到的真东西）

`probe-07-rendered-sweep.mjs` 在真 Chromium 里量真元素（底 = **从根往下把所有祖先背景按 alpha 合成**），
逮到两族静态面看不见的不达标：

| 选择器 | 实测底 | 现值 | 比值 |
|---|---|---|---|
| `.ref-pick-row .chip.out`（未选参考条目的平台胶囊） | `rgb(212,218,224)` | `--muted #59636e` | **4.34** ❌ |
| `.module-card .mc-deps`（依赖行） | 同上量级 | 同上 | **4.39** ❌ |

**静态面为什么看不见**：机械面按"同一条规则里的 `color` × `background`"配对，
而这两处的底是**两层叠出来的**（`--panel-2` 之上再叠一层淡底/淡色块）；
令牌面给 `--muted` 的假定底是**单个令牌**（`--bg` / `--panel` / `--panel-2`），
没算"叠一层"的情形。→ 修法：把浅色 `--muted` 压暗 5%（`#59636e → #555e68`），
实测底上 **4.68**（留余量）；暗色现值 5.26 不动。

跑法（仓库根）：
    python .scratch/light-contrast/apply-05a-muted-nested.py --check
    python .scratch/light-contrast/apply-05a-muted-nested.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

OLD_LIGHT = "--text: #1f2328; --muted: #59636e;"
NEW_LIGHT = "--text: #1f2328; --muted: #555e68;"
OLD_DARK = "--text: #e6edf3; --muted: #8b949e;"
NEW_DARK = "--text: #e6edf3; --muted: #919aa4;"
# 扫描还逮到一处：选中平台卡上的 .badge.ok（底 = accent-dim 叠卡片）——暗色 ok-text 4.20 ❌
OLD_OKTEXT = "--ok-text: #3fb950;"
NEW_OKTEXT = "--ok-text: #43c455;"
MEASURED_BG = {"light": (212, 218, 224), "dark": (41, 47, 54)}   # 扫描实测：两层叠出来的底


def main() -> None:
    check = "--check" in sys.argv
    text = L.read_page()
    if check:
        tok = L.Tokens(text)
        for theme, bg in MEASURED_BG.items():
            muted = tok.value("--muted", theme)[:3]
            r = L.contrast(muted, bg)
            if r < 4.5:
                raise SystemExit(f"复核不过：{theme} --muted {L.hexs(muted)} 压实测底只有 {r:.2f}（要 ≥4.5）")
            print(f"复核 OK：{theme} --muted {L.hexs(muted)} 压扫描实测底（rgb{bg}）= {r:.2f}")
        return
    problems, changed = [], 0
    for old, new in ((OLD_LIGHT, NEW_LIGHT), (OLD_DARK, NEW_DARK), (OLD_OKTEXT, NEW_OKTEXT)):
        if text.count(new) == 1 and text.count(old) == 0:
            continue                      # 已经改过了（本脚本可重入：先改亮色、再补暗色）
        n = text.count(old)
        if n != 1:
            problems.append(f"  锚点命中 {n} 次（期望 1）：{old}")
            continue
        text = text.replace(old, new)
        changed += 1
    if problems:
        raise SystemExit("锚点没命中，一个字节都没写：\n" + "\n".join(problems))
    L.PAGE.write_text(text, encoding="utf-8", newline="")
    print(f"已写盘：{L.PAGE.relative_to(L.ROOT)}（改了 {changed} 处：浅色 → #555e68、暗色 → #919aa4）")


if __name__ == "__main__":
    main()
