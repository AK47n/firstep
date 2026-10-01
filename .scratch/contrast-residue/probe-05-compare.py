"""contrast-residue 轮 · 05 号探针的读数半：板图焊盘 / 图例色点改前改后对照（工单 03）。

跑法（仓库根）：`python .scratch\\contrast-residue\\probe-05-compare.py`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent


def load(tag: str) -> dict:
    p = HERE / f"probe-05-pads-{tag}.json"
    if not p.is_file():
        raise SystemExit(f"读数不在：{p}（先跑 probe-05-pin-pad-colors.mjs --tag {tag}）")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    before, after = load("before"), load("after")
    print("=" * 78)
    print("§1 令牌值（页面根上的解析结果）")
    print("=" * 78)
    for b, a in zip(before["rows"], after["rows"]):
        t = b.get("theme")
        for tok in ("--pin-pad", "--pin-fixed-pad"):
            bv, av = b["tokens"].get(tok), a["tokens"].get(tok)
            mark = "不变" if bv == av else f"**{bv} → {av}**"
            print(f"  [{t}] {tok:<18} {mark}")

    print()
    print("=" * 78)
    print("§2 板图焊盘的计算填充色（`getComputedStyle().fill`，真 Chromium）")
    print("=" * 78)
    for b, a in zip(before["rows"], after["rows"]):
        t = b.get("theme")
        for kind in ("io", "fixed"):
            bv = (b["pads"].get(kind) or {}).get("fill")
            av = (a["pads"].get(kind) or {}).get("fill")
            mark = "不变" if bv == av else f"**{bv} → {av}**"
            print(f"  [{t}] {kind:<6} {mark}")

    print()
    print("=" * 78)
    print("§3 图例色点（同一令牌的两个落点，应与板图一致）")
    print("=" * 78)
    for b, a in zip(before["rows"], after["rows"]):
        t = b.get("theme")
        print(f"  [{t}] 改前 {[(d['label'], d['bg']) for d in b.get('dots', {}).get('legend', [])]}")
        print(f"  [{t}] 改后 {[(d['label'], d['bg']) for d in a.get('dots', {}).get('legend', [])]}")

    print()
    print("=" * 78)
    print("§4 真像素")
    print("=" * 78)
    for b, a in zip(before["rows"], after["rows"]):
        print(f"  [{b.get('theme')}] 板图 {b.get('shot')} → {a.get('shot')}")
        print(f"  [{b.get('theme')}] 图例 {b.get('legendShot')} → {a.get('legendShot')}")


if __name__ == "__main__":
    main()
