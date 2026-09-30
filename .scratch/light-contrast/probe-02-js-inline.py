"""浅色调色板轮 · 侦察探针（02）：渲染方（`static/js/**`）有没有内联取色声明。

**为什么要单独问一句**：描边那一轮（`border-guard/02`）实测渲染方有 **10 处内联整圈框**——
样式块面干净不代表渲染方干净。颜色这一面同理：守卫若只解析 `index.html` 的 `<style>` 块，
`static/js/**` 里那些 `style="color: var(--accent)"` 就是**射程外的漏网**。

读数三栏：
  ① 内联**声明式**取色（`style="…: var(--x)"` / `'#' 色值`）——守卫能不能静态看见；
  ② 内联**跨行拼接**出来的取色（`'…' + 'color: …'`）——与描边那条已知留白同类，抓不到；
  ③ 只用令牌、不带裸色值的处数（这类即使漏抓也不产生新的色对）。

跑法（仓库根）：
    python .scratch/light-contrast/probe-02-js-inline.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
JS_DIR = ROOT / "src" / "contest_generator" / "static" / "js"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

# `color:` / `background:` / `background-color:` 后面跟着取色值（令牌或字面色）
PROP_RE = re.compile(r"(?<![\w-])(color|background|background-color)\s*:\s*([^;\"']+)")
COLORISH = re.compile(r"var\(--|#[0-9a-fA-F]{3,8}\b|rgba?\(")


def main() -> None:
    print("=" * 78)
    print("浅色调色板轮 · 侦察读数（probe-02：渲染方内联取色声明）")
    print(f"扫描面：{JS_DIR.relative_to(ROOT)}/**.js")
    print("=" * 78)

    files = sorted(JS_DIR.rglob("*.js"))
    decl, concat, token_only = [], [], []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            for m in PROP_RE.finditer(line):
                val = m.group(2).strip()
                if not COLORISH.search(val) and "transparent" not in val and "inherit" not in val:
                    continue
                row = (p.relative_to(ROOT).as_posix(), i, m.group(1), val[:60])
                if val.startswith("var(--"):
                    token_only.append(row)
                else:
                    decl.append(row)
            # 跨行拼接：本行以 `+` 结尾且下一行出现取色属性 → 抓不到的那一类
            if re.search(r"\+\s*$", line) and i < len(text.splitlines()):
                nxt = text.splitlines()[i]
                if PROP_RE.search(nxt) and COLORISH.search(nxt):
                    concat.append((p.relative_to(ROOT).as_posix(), i, nxt.strip()[:60]))

    print(f"\n## ① 内联取色、值**不是**纯令牌（含裸色值 / rgba / 混写）—— 共 **{len(decl)}** 处\n")
    for f, i, prop, val in decl:
        print(f"  {f}:{i}  {prop}: {val}")

    print(f"\n## ② 内联取色、值就是 `var(--x)` 令牌 —— 共 **{len(token_only)}** 处\n")
    from collections import Counter
    cnt = Counter(v.split(")")[0] + ")" for _, _, _, v in token_only)
    for tok, n in cnt.most_common():
        print(f"  {tok:<34} × {n}")
    print("\n  （只列令牌计数；逐条清单要看时把上面 `decl` 改成 `token_only` 再跑）")

    print(f"\n## ③ 跨行拼接出来的取色声明 —— 共 **{len(concat)}** 处（**静态守卫抓不到**，与描边留白同类）\n")
    for f, i, nxt in concat[:40]:
        print(f"  {f}:{i}  → {nxt}")

    print("\n## 结论口径\n")
    print(f"  · ① 类 {len(decl)} 处是**真漏网**候选：静态守卫只解析 `<style>` 块，看不见它们；")
    print(f"  · ② 类 {len(token_only)} 处不产生新色对（值仍是令牌），但要判它压在什么底上只能靠渲染测量；")
    print(f"  · ③ 类 {len(concat)} 处是**已知留白**（守卫明文不判），探针每轮盯着它有没有变多。")


if __name__ == "__main__":
    main()
