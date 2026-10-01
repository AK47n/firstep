"""contrast-residue 轮 · 09 号探针：`li.cant` 的**真像素读数**（工单 05）。

读 `probe-08-shots-cant.json`（probe-08 扩口径之后的输出），把
`.pin-menu-list li.cant` 那一族（整行 + 它的文字子元素）逐格算比值，
并与静态族面同一对色（`--muted` × `--panel-2`）对账。

跑法（仓库根）：`python .scratch\\contrast-residue\\probe-09-cant-readings.py`
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROBE_LIB = ROOT / ".scratch" / "light-contrast" / "probe_lib.py"
SHOTS = HERE / "probe-08-shots-cant.json"

spec = importlib.util.spec_from_file_location("_contrast_probe_lib", PROBE_LIB)
plib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plib)

RGB_RE = re.compile(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)")


def rgb(text: str):
    m = RGB_RE.search(text or "")
    if not m:
        return None
    r, g, b, a = m.groups()
    return (int(float(r)), int(float(g)), int(float(b)), float(a) if a is not None else 1.0)


def main() -> None:
    data = json.loads(SHOTS.read_text(encoding="utf-8"))
    text = plib.read_page()
    tok = plib.Tokens(text)
    # ⚠ 认人键是 `form`（= 登记表里那条选择器）；`sel` 是**实际命中的那个元素**的路径
    # （`.pin-menu > .pin-menu-list > .cant`），第一版按 `sel` 过滤，一格都没认到。
    rows = [s for s in data["shots"] if (s.get("form") or "") == ".pin-menu-list li.cant"]
    print("=" * 100)
    print(f"§1 `li.cant` 的真像素（{SHOTS.name}，probe-08 探针；命中 {len(rows)} 格）")
    print("=" * 100)
    print(f"{'主题':<6}{'元素':<26}{'字色':<22}{'底':<26}{'比值':<8}文本")
    for s in sorted(rows, key=lambda x: (x.get("theme", ""), x.get("slug", ""), x.get("tag", ""))):
        a = rgb(s.get("color") or "")
        bg = rgb(s.get("background") or "")
        theme = s.get("theme") or ""
        if a is None:
            print(f"{theme:<6}{s.get('slug',''):<26}（无色）")
            continue
        if bg is None or bg[3] < 1:
            # 透明底 ⇒ 吃整行那一层（登记表里写的假定底 = `--panel-2`）
            base = tok.value("--panel-2", theme)[:3]
            eff = plib.over(bg, base) if bg else base
        else:
            eff = bg[:3]
        ratio = plib.contrast(a[:3], eff)
        print(f"{theme:<6}{s.get('slug',''):<26}{s.get('color',''):<22}{s.get('background',''):<26}"
              f"{ratio:<8.2f}{(s.get('text') or '')[:22]}")

    print()
    print("=" * 100)
    print("§2 与静态族面同一对色对账（`--muted` × `--panel-2`）")
    print("=" * 100)
    for theme in ("light", "dark"):
        muted = tok.value("--muted", theme)[:3]
        p2 = tok.value("--panel-2", theme)[:3]
        print(f"  [{theme:<5}] --muted {plib.hexs(muted)} × --panel-2 {plib.hexs(p2)} = "
              f"{plib.contrast(muted, p2):.2f}")

    print()
    print("=" * 100)
    print("§3 探针自己记的账（准备 / 没量到）")
    print("=" * 100)
    for p in data.get("prepares", []):
        print(f"  [{p.get('theme','')}] {p.get('note','')}")
    overlay_missing = [n for n in data.get("notes", [])
                       if n.get("scope") == "overlay" and (n.get("skipped") or 0)]
    for n in overlay_missing:
        print(f"  没量到（浮层 [{n.get('theme','')}]）：{n.get('skipped')} 格 —— "
              + "、".join(f"{k}×{v}" for k, v in (n.get("skippedDetail") or {}).items()) if False else
              f"  没量到（浮层 [{n.get('theme','')}]）：{n.get('skipped')} 格（含 MAX_FORM_SHOTS 上限）")


if __name__ == "__main__":
    main()
