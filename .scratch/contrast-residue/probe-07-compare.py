"""contrast-residue 轮 · 07 号探针的读数半：三条真文字的改前 / 改后**比值**（工单 04）。

口径：把探针量到的 `color` / `opacity` / `backdrop`（往上找到的第一层不透明底；半透明的
再叠到 `--panel` 上）用 `probe_lib` 的同一套公式算比值——
**改前往字上拉平**（`opacity` 是合成运算，静态面算不出），**改后**就是声明色压底。

跑法（仓库根）：`python .scratch\\contrast-residue\\probe-07-compare.py`
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

spec = importlib.util.spec_from_file_location("_contrast_probe_lib", PROBE_LIB)
plib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plib)

RGB_RE = re.compile(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)")


def rgb(text: str):
    m = RGB_RE.search(text or "")
    if not m:
        return None
    r, g, b, a = m.groups()
    return (float(r), float(g), float(b), float(a) if a is not None else 1.0)


def load(tag: str) -> dict:
    p = HERE / f"probe-07-muted-text-{tag}.json"
    if not p.is_file():
        raise SystemExit(f"读数不在：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    before, after = load("before"), load("after")
    text = plib.read_page()
    tok = plib.Tokens(text)
    rows = []
    for b, a in zip(before["rows"], after["rows"]):
        theme = b["theme"]
        panel = plib.over(tok.value("--panel", theme)[:3], (255, 255, 255)) \
            if False else tok.value("--panel", theme)[:3]
        for key, label in (("unsel", ".chip.rec.unsel .reason"), ("sugg", ".sugg-count"),
                           ("soft", ".res-soft")):
            bm, am = b.get(key, {}), a.get(key, {})
            if bm.get("missing") or am.get("missing"):
                rows.append((theme, label, "没量到", bm.get("missing") or am.get("missing")))
                continue
            bg_raw = rgb(bm["backdrop"]) or (0, 0, 0, 1)
            bg = plib.over(bg_raw, panel) if bg_raw[3] < 1 else bg_raw[:3]
            bg = tuple(int(round(v)) for v in bg)      # `hexs` 要整数（`over` 可能给 float）
            fg = tuple(int(round(v)) for v in rgb(bm["color"])[:3])
            op = float(bm["opacity"])
            fg_before = tuple(int(op * fg[i] + (1 - op) * bg[i]) for i in range(3))
            ratio_before = plib.contrast(fg_before, bg)
            fg_after = tuple(int(round(v)) for v in rgb(am["color"])[:3])
            ratio_after = plib.contrast(fg_after, bg)
            rows.append((theme, label, f"{ratio_before:.2f} → {ratio_after:.2f}",
                         f"opacity {op:g} → {am['opacity']}；底 {plib.hexs(bg)}"))

    print("=" * 96)
    print("§1 三条真文字：改前（带 opacity 的合成）/ 改后（声明色压底）比值")
    print("=" * 96)
    for theme, label, ratio, note in rows:
        print(f"  [{theme:<5}] {label:<28} {ratio:<16} {note}")
    print()
    print("=" * 96)
    print("§2 真像素（改前 / 改后各一张，文件名带 tag）")
    print("=" * 96)
    for b, a in zip(before["rows"], after["rows"]):
        print(f"  [{b['theme']}] unsel {b.get('unselShot')} → {a.get('unselShot')}")
        print(f"  [{b['theme']}] sugg  {b.get('suggShot')} → {a.get('suggShot')}")
    print()
    print("判读：三条里两条（`.chip.rec.unsel .reason` / `.sugg-count`）拿到了真像素；"
          "`.res-soft` **没量到**——它要一份带 AI 洞察的任务计划（资源总览是纯前端聚合），"
          "本流程到不了那里。替代依据写在工单票尾。")


if __name__ == "__main__":
    main()
