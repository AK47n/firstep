"""contrast-residue 轮 · 01 号探针：**令牌解析面**扩面前后的对照读数（工单 01）。

口径：旧面 = 只取**第一个** `:root`（`re.search`，即工单 01 之前的口径）；
新面 = 合并**全部** `:root`（`probe_lib.Tokens`，后者覆盖前者）。

跑法（仓库根）：`python .scratch\\contrast-residue\\probe-01-token-face.py`
读数落在同目录 `probe-01-token-face.txt`（重定向即可）。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PROBE_LIB = ROOT / ".scratch" / "light-contrast" / "probe_lib.py"

spec = importlib.util.spec_from_file_location("_contrast_probe_lib", PROBE_LIB)
plib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plib)


def old_face(text: str) -> dict[str, dict[str, str]]:
    """旧口径：**只取第一个** `:root` / 亮色块（工单 01 之前两侧都是这么写的）。"""
    out: dict[str, dict[str, str]] = {"dark": {}, "light": {}}
    for theme, block in (("dark", plib.BLOCK_ROOT), ("light", plib.BLOCK_LIGHT)):
        m = block.search(text)
        if not m:
            raise SystemExit(f"解析不到 {theme} 令牌块")
        for name, val in plib.TOKEN_RE.findall(m.group(1)):
            out[theme][name] = val.strip()
    return out


def main() -> None:
    text = plib.read_page()
    css = plib.contrast_style_text(text)
    before = old_face(text)
    after = plib.Tokens(text)

    print("=" * 78)
    print("§1 解析面扩面前后：令牌数")
    print("=" * 78)
    for theme in ("dark", "light"):
        b, a = len(before[theme]), len(after.raw[theme])
        print(f"  [{theme}] 旧面 {b} → 新面 {a}（+{a - b}）")

    print()
    print("=" * 78)
    print("§2 新面多出来的令牌（旧面查无此值 ⇒ 判据**静默不判**）")
    print("=" * 78)
    late = [n for n in after.raw["dark"] if n not in before["dark"]]
    print(f"  暗色多出 {len(late)} 个：")
    for name in late:
        light_over = after.raw["light"].get(name)
        mark = f"亮色覆盖 → {light_over}" if light_over else "**亮色未覆盖**（沿用暗色值）"
        print(f"    {name:<20} {after.raw['dark'][name]:<34} {mark}")

    print()
    print("=" * 78)
    print("§3 两个图例色点的令牌：解出来了（工单 03 的前置）")
    print("=" * 78)
    for name in ("--pin-pad", "--pin-fixed-pad"):
        for theme in ("dark", "light"):
            v = after.value(name, theme)
            got = "解不出" if v is None else plib.hexs(v)
            print(f"  [{theme}] {name:<20} {got}")

    print()
    print("=" * 78)
    print("§4 定义面（工单 02 的底座）：任意块里的 `--x:` 都算")
    print("=" * 78)
    defined = plib.defined_token_names(css)
    print(f"  任意块里定义过的令牌名 = **{len(defined)}** 个"
          f"（令牌块里只有 {len(after.raw['dark'])} + {len(after.raw['light'])} 个）")
    scoped = sorted(n for n in defined if n not in after.raw["dark"] and n not in after.raw["light"])
    print(f"  只在**类作用域**里定义的 = {len(scoped)} 个：{'、'.join(scoped) if scoped else '（无）'}")
    print("  ⇒ 这解释了为什么定义面不能按'只认令牌块'算："
          "`--code-font-size`（×6）与 `--hwcheck-title-mark`（×1）就是这一类，"
          "按令牌块算会得到 2 处**假阳性**。")

    print()
    print("=" * 78)
    print("§5 冻结数：扩面之后**应当一个都不变**")
    print("=" * 78)
    pairs = plib.contrast_pairs(text, after)
    cells = plib.contrast_family_cells(text, after)
    print(f"  机械面对数 = {len(pairs)}；族面格数 = {len(cells)}")
    print("  （对照：守卫里冻结的是 394 / 172——扩面**不新增**取色对，"
          "因为 `--pin-*` 一族只出现在渲染方与 SVG 属性里，样式块里没有它们的取色规则）")
    roots = plib.BLOCK_ROOT.findall(text)
    print(f"  `:root` 块数 = {len(roots)}（≥2 才有扩面这回事；只剩 1 个 = 第二块被搬走了）")


if __name__ == "__main__":
    main()
