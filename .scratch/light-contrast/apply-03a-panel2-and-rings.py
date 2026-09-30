"""浅色调色板轮 · 施工脚本（03 单）：浅色 `--panel-2` 加深 + 焦点环提到 3:1 以上。

## 两件事

1. **`--panel-2` 加深**（浅色 `#eef1f4 → #e1e6ec`）：与页面底比值 **×1.065 → ×1.179**
   （暗色现值 ×1.17，两边同水平）。联动复核过：`--muted` 压上去仍 **4.87**；
   六族 `-text` 的落定值本来就是按这个目标底留的余量（最坏 ≥4.8），**不需要重算**。
2. **非文字 3:1**：加深之后 `--accent` 压在淡底上从 2.99 掉到 **2.70**（< 3.0）。
   本脚本只动**焦点环 / 定位环**（11 处 `outline` / `outline-color`）——那是键盘可达性的硬需求，
   改走 `--accent-text`（压淡底 **5.53**、压白 **5.9**）。
   **控件普通描边（47 处 `border-color`）与语义左条（7 处 `border-left`）留在主令牌**，
   并在守卫的族表里如实登记为 `nontext` 债（理由写在表里）——它们装饰性强于信息性，
   大面积改深会动整页观感，属另一件事。

跑法（仓库根）：
    python .scratch/light-contrast/apply-03a-panel2-and-rings.py --check
    python .scratch/light-contrast/apply-03a-panel2-and-rings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

EDITS = [
    # ① 浅色淡底加深（只动亮色块那一行：暗色块里的 --panel-2 是 #1c2128，字面不同）
    ("--bg: #f6f8fa; --panel: #ffffff; --panel-2: #eef1f4;",
     "--bg: #f6f8fa; --panel: #ffffff; --panel-2: #e1e6ec;", 1),
    # ② 焦点环 / 定位环改走文字档（键盘可达性硬需求，提到 3:1 以上）
    ("outline: 2px solid var(--accent)", "outline: 2px solid var(--accent-text)", 9),
    ("outline-color: var(--accent)", "outline-color: var(--accent-text)", 2),
]


def main() -> None:
    check = "--check" in sys.argv
    raw = L.PAGE.read_bytes()
    nls = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8")

    if check:
        problems = []
        if "--panel-2: #e1e6ec;" not in text:
            problems.append("  浅色 --panel-2 没改到 #e1e6ec")
        if "outline: 2px solid var(--accent-text)" not in text:
            problems.append("  焦点环没改走 --accent-text")
        if "outline: 2px solid var(--accent)" in text or "outline-color: var(--accent)" in text:
            problems.append("  还有 outline 用主令牌（那一条在淡底上只有 2.70）")
        # 复核联动数字（这是本单的判据，不是装饰）
        tok = L.Tokens(text)
        bg = tok.value("--bg", "light")[:3]
        p2 = tok.value("--panel-2", "light")[:3]
        if L.contrast(p2, bg) < 1.15:
            problems.append(f"  淡底与页面底只有 ×{L.contrast(p2, bg):.3f}（目标 ≥1.15）")
        for name, floor in (("--muted", 4.5), ("--accent-text", 4.5)):
            r = L.contrast(tok.value(name, "light")[:3], p2)
            if r < floor:
                problems.append(f"  {name} 压淡底只有 {r:.2f}（要 ≥{floor}）")
        if problems:
            raise SystemExit("复核发现问题：\n" + "\n".join(problems))
        print(f"复核 OK：淡底 ×{L.contrast(p2, bg):.3f}；--muted {L.contrast(tok.value('--muted','light')[:3], p2):.2f}、"
              f"--accent-text {L.contrast(tok.value('--accent-text','light')[:3], p2):.2f} 压上去都过线")
        return

    problems = []
    for old, new, want in EDITS:
        n = text.count(old)
        if n != want:
            problems.append(f"  命中 {n} 次（期望 {want}）：{old[:70]}")
            continue
        text = text.replace(old, new)
    if problems:
        raise SystemExit("锚点没命中，一个字节都没写：\n" + "\n".join(problems))
    L.PAGE.write_bytes(text.encode("utf-8"))
    print(f"已写盘：{L.PAGE.relative_to(L.ROOT)}；改了 {len(EDITS)} 类锚点"
          f"（淡底 1 处 + 焦点环 {EDITS[1][2]} 处 + 动画关键帧 {EDITS[2][2]} 处）")


if __name__ == "__main__":
    main()
