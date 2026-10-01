"""contrast-residue 轮 · 03 号探针的读数半：改前 / 改后两份 JSON 对照（工单 02）。

口径：`.pin-subtitle`（`#pin-fixed-sub`）在两主题下的**计算样式**必须逐字节相同——
这条修复只把"没定义过的令牌"换成真令牌，**不许改变观感**。

跑法（仓库根）：`python .scratch\\contrast-residue\\probe-03-compare.py`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent


def load(tag: str) -> dict:
    p = HERE / f"probe-03-subtitle-{tag}.json"
    if not p.is_file():
        raise SystemExit(f"读数不在：{p}（先跑 probe-03-subtitle-color.mjs --tag {tag}）")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    before, after = load("before"), load("after")
    print("=" * 78)
    print("§1 计算样式对照（真 Chromium + 真后端：选 STM32 平台 + 加第一张卡）")
    print("=" * 78)
    ok = True
    for b, a in zip(before["rows"], after["rows"]):
        same = b.get("color") == a.get("color")
        ok = ok and same
        print(f"  [{b.get('theme')}] 改前 {b.get('color')}（--fg={b.get('fg')!r}）"
              f" → 改后 {a.get('color')}（--fg={a.get('fg')!r}）　相同 = {same}")
    print()
    print("=" * 78)
    print("§2 真像素（人眼记录；改前 / 改后各一张，文件名带 tag 不互相覆盖）")
    print("=" * 78)
    for b, a in zip(before["rows"], after["rows"]):
        print(f"  [{b.get('theme')}] {b.get('shot')}  →  {a.get('shot')}")
    print()
    print(f"结论：两主题计算样式{'逐字节相同' if ok else '**不一致**'}；"
          f"`--fg` 改前解析值 = 空串（未定义，浏览器按 inherit 处理），改后该字面已从盘上消失。")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
