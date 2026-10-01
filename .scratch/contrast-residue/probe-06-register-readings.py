"""contrast-residue 轮 · 06 号探针：**渲染方登记表**的形状读数（工单 03）。

从守卫源码里读（单源，**不另抄一份名单**）：
  · `JS_CONTRAST_KINDS`（档位表）与 `JS_CONTRAST_REGISTER`（19 条登记）逐条计数；
  · `skip` 的实例数（工单 03 之后应为 **0**——零实例的档位不留）；
  · 两个图例色点的档位（应为 `surface-bordered`）；
并顺带现算机械面对数 / 族面格数（冻结值 394 / 172，扩面与换档都**不该**动它们）。

跑法（仓库根）：`python .scratch\\contrast-residue\\probe-06-register-readings.py`
"""
from __future__ import annotations

import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"
PROBE_LIB = ROOT / ".scratch" / "light-contrast" / "probe_lib.py"

spec = importlib.util.spec_from_file_location("_contrast_probe_lib", PROBE_LIB)
plib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plib)


def main() -> None:
    js = GUARD.read_text(encoding="utf-8")
    m = re.search(r"const JS_CONTRAST_KINDS = \[([^\]]*)\];", js)
    if not m:
        raise SystemExit("守卫里找不到 `JS_CONTRAST_KINDS`——格式变了")
    kinds = re.findall(r'"([^"]+)"', m.group(1))
    m = re.search(r"const JS_CONTRAST_REGISTER = \[([\s\S]*?)\n\];", js)
    if not m:
        raise SystemExit("守卫里找不到 `JS_CONTRAST_REGISTER`——格式变了")
    rows = re.findall(r'^\s*\["([^"]+)",\s*\'([^\']*)\',\s*"(--[a-z0-9-]+)",\s*"(--[a-z0-9-]+)",\s*"([^"]+)"\],?$',
                      m.group(1), re.M)
    if len(rows) < 15:
        raise SystemExit(f"只解析出 {len(rows)} 条渲染方登记（19 条上下）——格式变了")

    print("=" * 78)
    print("§1 渲染方登记表形状")
    print("=" * 78)
    print(f"  档位表 JS_CONTRAST_KINDS = {kinds}")
    print(f"  登记条数 = **{len(rows)}**")
    counts = Counter(k for *_, k in rows)
    for k, n in sorted(counts.items()):
        print(f"    {k:<18} {n} 条")
    print(f"  `skip` 实例数 = **{counts.get('skip', 0)}**"
          + "（工单 03 之后应为 0：零实例的档位不留）")

    print()
    print("=" * 78)
    print("§2 两个图例色点（工单 03 的靶子）")
    print("=" * 78)
    for file, anchor, token, base, kind in rows:
        if "background:var(--pin" in anchor:
            print(f"  {token:<18} {kind:<18} 底 {base:<9} 锚点 {anchor[:52]}…")

    print()
    print("=" * 78)
    print("§3 冻结数（换档与扩面都应该**不动**它们）")
    print("=" * 78)
    text = plib.read_page()
    tok = plib.Tokens(text)
    print(f"  机械面对数 = {len(plib.contrast_pairs(text, tok))}（冻结 394）")
    print(f"  族面格数   = {len(plib.contrast_family_cells(text, tok))}（冻结 172）")
    print(f"  `:root` 块数 = {len(plib.BLOCK_ROOT.findall(text))}（扩面之后应为 2）")


if __name__ == "__main__":
    main()
