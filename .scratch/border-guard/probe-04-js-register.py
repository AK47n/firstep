r"""描边守卫轮 · 读数探针（02 单）：**渲染方登记簿 ↔ 盘上**双向对账 + 每类条数 + 口径脚注。

口径：
  · 盘上那一边 = `scope_lib.js_inline_border_entries()`（`static/js/**` 逐行扫 `border:` 简写、
    值非 none/0；取值终止符是 `;` **或** `"`——内联样式写在 HTML 属性里）。
  · 登记簿那一边 = 守卫源码里的 `JS_BORDER_REGISTER`（**单一出处**，本探针不另抄）。
  · 对账是**多重集**：同一锚点登记 N 条，盘上就得有 N 行（`.role-type` 那条是两个渲染函数
    各写了一遍，逐字相同）。

它回答四件事：
  ① 双向差（盘上没登记 / 登记项过期）——守卫腿⑦ 的判据，这里给**逐条明细**；
  ② 每类条数（与样式块面**共用** `BORDER_KINDS`）；
  ③ 逐条清单（文件 / 行号 / 取值 / 认领它的锚点）；
  ④ 脚注：`static/js/**` 里那些**单边分隔线**（`border-top` / `border-bottom`）有几条
     ——它们是"一条分隔线"，**本来就不在"整圈完整框"口径里**，量出来免得被读成漏网。
"""

from __future__ import annotations

import collections
import datetime
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "ui-density-sitewide"))

from scope_lib import (  # noqa: E402
    DEAD_BORDER, JS_BORDER_LINE_RE, js_files, js_inline_border_entries,
    load_border_kinds, load_js_border_register,
)

OUT = HERE / "probe-04-js-register.txt"
# —— 下面两条**只给「覆盖审计」用**，不是口径：口径那条是 `JS_BORDER_LINE_RE`（import 来的）。
# 它们是**更宽**的审计网（认单边后缀、认冒号前空格），用来回答"有没有口径漏掉的写法"。
EDGE_RE = re.compile(r"(?<![\w-])border-(?:top|right|bottom|left):\s*([^;\"]+)")
ANY_BORDER_RE = re.compile(r"\bborder(?:-(?:top|right|bottom|left))?\s*:")


def main() -> int:
    kinds = load_border_kinds()
    register = load_js_border_register()
    disk = js_inline_border_entries()
    kind_ids = {k for k, _why in kinds}

    want = collections.Counter((f, a) for f, a, _k in register)
    got: collections.Counter[tuple[str, str]] = collections.Counter()
    unregistered: list[dict] = []
    ambiguous: list[tuple[dict, list[str]]] = []
    claimed: list[tuple[dict, str]] = []
    for e in disk:
        hits = [key for key in want if key[0] == e["file"] and key[1] in e["raw"]]
        if not hits:
            unregistered.append(e)
        elif len(hits) > 1:
            ambiguous.append((e, [a for _f, a in hits]))
        else:
            got[hits[0]] += 1
            claimed.append((e, hits[0][1]))
    stale = [(key, want[key] - got.get(key, 0)) for key in want if got.get(key, 0) < want[key]]

    lines: list[str] = []
    add = lines.append
    add("# 读数：描边守卫轮 · 渲染方登记簿 ↔ 盘上双向对账")
    add("# 命令：python .scratch/border-guard/probe-04-js-register.py")
    add("# 口径：scope_lib.js_inline_border_entries（逐行扫 border: 简写，取值终止符 ; 或 \"）")
    add(f"# 时间：{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}")
    add("")
    add(f"盘上渲染方内联整圈框：{len(disk)} 条")
    add(f"渲染方登记簿登记项　：{len(register)} 条")
    add(f"双向差　　　　　　　：盘上未登记 {len(unregistered)} 条 / 登记项过期 {len(stale)} 条"
        f" / 锚点歧义 {len(ambiguous)} 条")
    for e in unregistered:
        add(f"  [未登记] {e['file']}:{e['line']} → {e['value']}")
    for (f, a), miss in stale:
        add(f"  [过期]   {f} / {a}（差 {miss} 行）")
    for e, hits in ambiguous:
        add(f"  [歧义]   {e['file']}:{e['line']} 命中 {len(hits)} 条锚点：{hits}")

    dist = collections.Counter(k for _f, _a, k in register)
    add("")
    add("## 每类条数（与样式块面共用 BORDER_KINDS）")
    for kid, why in kinds:
        if dist.get(kid):
            add(f"  {kid:10s} {dist[kid]:3d}   {why}")
    for kid in sorted(set(dist) - kind_ids):
        add(f"  ⚠ 未定义的类别：{kid}（{dist[kid]} 条）")

    add("")
    add("## 逐条清单（文件 / 行号 / 取值 / 认领它的锚点）")
    for e, anchor in sorted(claimed, key=lambda x: (x[0]["file"], x[0]["line"])):
        add(f"  {e['file']}:{e['line']}  {e['value']:32s}  ← {anchor[:64]}")

    add("")
    add("## 脚注：渲染方里的单边分隔线（不在口径内，别读成漏网）")
    edges: list[tuple[str, int, str]] = []
    for rel, text in js_files():
        for i, raw in enumerate(text.split("\n"), start=1):
            for m in EDGE_RE.finditer(raw):
                edges.append((rel, i, m.group(1).strip()))
    for rel, i, value in edges:
        add(f"  {rel}:{i}  {value}")
    add(f"  合计 {len(edges)} 条——`border-top` / `border-bottom` 是**一条分隔线**，"
        f"不是「整圈完整框」；`full_borders` / 本口径都只认 `border:` 简写。")

    # 覆盖审计：把 `border…:` 的**全部**行次按几种写法拆开，证明"10 条"不是漏扫出来的
    add("")
    add("## 覆盖审计（`border…:` 的每一处都归了类，没有「没归类的」）")

    def classify(raw: str) -> tuple[int, int, int]:
        """→ (入册的整圈完整框, 撤框, 单边分隔线)。前两项**用口径那条正则**（import 来的），
        不与 `js_inline_border_entries()` 分叉；第三项是审计网（口径之外、明写不在射程的那类）。"""
        full = dead = 0
        for m in JS_BORDER_LINE_RE.finditer(raw):
            value = (m.group(1) or m.group(2) or "").strip()
            if not value:
                continue
            if value.split()[0] in DEAD_BORDER:
                dead += 1
            else:
                full += 1
        return full, dead, len(EDGE_RE.findall(raw))

    tallies = collections.Counter()
    unclassified: list[tuple[str, int, str]] = []
    for rel, text in js_files():
        for i, raw in enumerate(text.split("\n"), start=1):
            n_any = len(ANY_BORDER_RE.findall(raw))
            if not n_any:
                continue
            n_full, n_dead, n_edge = classify(raw)
            tallies["行次（含 border…: 的行）"] += 1
            tallies["整圈完整框（入册）"] += n_full
            tallies["撤框（none / 0 开头）"] += n_dead
            tallies["单边分隔线"] += n_edge
            if n_full + n_dead + n_edge < n_any:
                unclassified.append((rel, i, raw.strip()[:100]))
    for k, v in tallies.items():
        add(f"  {k}：{v}")
    if unclassified:
        add(f"  ⚠ 有 {len(unclassified)} 处 `border…:` 没被上面任何一类收走（口径可能漏了写法）：")
        for rel, i, raw in unclassified[:10]:
            add(f"      {rel}:{i}  {raw}")
    else:
        add("  ✅ 每一处 `border…:` 都落在「入册 / 撤框 / 单边」三类里，没有漏扫的写法。")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for line in lines:
        if line and not line.startswith("#"):
            print(line)
    print(f"\n已落盘：{OUT.relative_to(ROOT).as_posix()}")
    return 1 if (unregistered or stale or ambiguous) else 0


if __name__ == "__main__":
    raise SystemExit(main())
