"""contrast-residue 轮 · 00 号探针：**令牌定义面**的侦察（clarify / spec 期用）。

回答两个问题（都是 A 组的票面依据）：

1. **A6**：第二个 `:root` 块（页面作用域那个）里定义了哪些令牌？现有解析面
   （只取**第一个** `:root`）看不见它们——把它们列出来，并标"亮色块有没有覆盖"
   （没覆盖 = 亮色下沿用暗色值，这就是 `--pin-fixed-pad` 那个疑点）。
2. **A5**：页面 `<style>` + `static/js/**` 里**用到**的 `var(--name)`，有多少个
   名字在**任何**令牌块里都没有定义（= 笔误面）。`--fg` 是已知的一个。

跑法（仓库根）：`python .scratch\\contrast-residue\\probe-00-recon.py`
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

# 本机控制台是 GBK：不换成 UTF-8 的话，报告里的 `⇒` / `✗` 会在 print 上抛
# UnicodeEncodeError（`docs/agents/local-environment.md` 记过这条本机事实）。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
JS_DIR = ROOT / "src" / "contest_generator" / "static" / "js"

BLOCK_ROOT = re.compile(r"\n {2}:root \{([\s\S]*?)\n {2}\}", re.S)
BLOCK_LIGHT = re.compile(r'\n {2}html\[data-theme="light"\] \{([\s\S]*?)\n {2}\}', re.S)
TOKEN_RE = re.compile(r"(--[a-z0-9-]+):\s*([^;]+);")
#: 取色/取值用法：`var(--name)` 与 `var(--name, 兜底)` 分开记（兜底那条**不算**未定义）。
VAR_USE = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*(,)?")
STYLE_BLOCK = re.compile(r"<style>([\s\S]*?)</style>")


def token_blocks(text: str):
    """→ `(roots, lights)`：**全部** `:root` / 亮色块的原文列表（现有解析面只取第一个）。"""
    return BLOCK_ROOT.findall(text), BLOCK_LIGHT.findall(text)


def tokens_of(blocks):
    out: dict[str, str] = {}
    for b in blocks:
        for name, val in TOKEN_RE.findall(b):
            out[name] = val.strip()  # 后者覆盖前者（与 CSS 同特异性下的源序一致）
    return out


def main() -> None:
    text = PAGE.read_text(encoding="utf-8")
    roots, lights = token_blocks(text)
    first_root = tokens_of(roots[:1])
    all_root = tokens_of(roots)
    light = tokens_of(lights)

    print("=" * 78)
    print("§1 令牌块盘点")
    print("=" * 78)
    print(f"  `:root` 块 {len(roots)} 个（解析面旧口径只取第 1 个）"
          f"；亮色块 {len(lights)} 个")
    print(f"  第 1 个 `:root` 定义 {len(first_root)} 个令牌；全部 `:root` 合计 {len(all_root)} 个")

    only_later = {k: v for k, v in all_root.items() if k not in first_root}
    print(f"\n  ⇒ **只在后面的 `:root` 块里定义**（旧解析面看不见）= {len(only_later)} 个：")
    for name, val in sorted(only_later.items()):
        over = light.get(name)
        mark = f"亮色覆盖 → {over}" if over else "**亮色未覆盖**（沿用这里的值）"
        print(f"    {name:<20} {val:<34} {mark}")

    print()
    print("=" * 78)
    print("§2 页面/JS 里 `var(--x)` 的未定义面（A5 的规模）")
    print("=" * 78)
    style = STYLE_BLOCK.search(text)
    sources: list[tuple[str, str]] = [("index.html:<style>", style.group(1) if style else "")]
    for p in sorted(JS_DIR.rglob("*.js")):
        sources.append((str(p.relative_to(ROOT)).replace("\\", "/"), p.read_text(encoding="utf-8")))

    defined = set(all_root) | set(light)
    missing: Counter[tuple[str, str]] = Counter()
    for label, src in sources:
        for m in VAR_USE.finditer(src):
            name, has_fallback = m.group(1), bool(m.group(2))
            if name in defined or has_fallback:
                continue
            missing[(name, label)] += 1
    if not missing:
        print("  未定义（且无兜底）的令牌：**0 处**")
    else:
        print(f"  未定义（且无兜底）的令牌用法：**{len(missing)} 个「令牌 × 文件」组合**")
        for (name, label), n in sorted(missing.items()):
            print(f"    {name:<20} {label:<44} ×{n}")
        byname = Counter(n for (n, _l) in missing)
        print("\n  按令牌名合计：" + "、".join(f"{n} ×{c}" for n, c in sorted(byname.items())))

    print()
    print("=" * 78)
    print("§2b 把定义面扩到**任意 CSS 块**（类作用域也算）之后，还剩几处无兜底未定义")
    print("=" * 78)
    # 「定义面」= 任意规则体里出现的 `--x:`（`:root` / 亮色块 / `.some-class` / `#id` 都算）。
    # 这是 A5 那条守卫的正确底座：`var(--code-font-size)` 那种**类作用域定义**是合法写法，
    # 只按令牌块找会把它们误判成笔误（本探针 §2 就是这么报的——两个假阳性）。
    scoped = set(TOKEN_RE.findall(style.group(1) if style else ""))
    scoped_names = {name for name, _ in scoped}
    still = Counter()
    for label, src in sources:
        for m in VAR_USE.finditer(src):
            name, has_fallback = m.group(1), bool(m.group(2))
            if has_fallback or name in scoped_names:
                continue
            still[(name, label)] += 1
    if not still:
        print("  无兜底且**任何块里都没定义**的用法：**0 处**")
    else:
        print(f"  无兜底且任何块里都没定义的用法：**{len(still)} 个「令牌 × 文件」组合**")
        for (name, label), n in sorted(still.items()):
            print(f"    {name:<20} {label:<44} ×{n}")

    print()
    print("=" * 78)
    print("§3 只用兜底值写法的 `var(--x, …)`（不算未定义，但值得看一眼）")
    print("=" * 78)
    fb: Counter[str] = Counter()
    for _label, src in sources:
        for m in VAR_USE.finditer(src):
            if m.group(2):
                fb[m.group(1)] += 1
    for name, n in sorted(fb.items()):
        if name not in defined:
            print(f"    {name:<20} ×{n}（令牌不存在，渲染吃兜底值）")
    print("  " + ("（没有这种）" if not any(n not in defined for n in fb) else ""))


if __name__ == "__main__":
    main()
