r"""描边守卫轮 · 读数探针（01 单）：**登记簿 ↔ 盘上**双向对账 + 每类条数 + 口径分列。

口径：
  · 盘上那一边 = `scope_lib.full_border_entries()`（判据站在 `full_borders` 上：完整 `border:`
    声明、值非 none/0；多两步 = 剥前导块注释 + 附作用域与"含不含 transparent"）。
  · 登记簿那一边 = 守卫源码里的 `BORDER_KINDS` / `BORDER_REGISTER`（**单一出处**，本探针不另抄）。

它回答四件事：
  ① 双向差（盘上没登记 / 登记项过期）——那正是守卫腿⑥ 的判据，这里给的是**逐条明细**；
  ② 每类条数（类别表形状的读数）；
  ③ **口径分列**：115 条完整框 = 94 条可见框 + 21 条非框（12 占位 + 9 图形件）
     ——"整圈完整框 115"是**声明数**口径，别与"渲染出来的框元素数"混读；
  ④ 脚注：`placeholder` 那 12 条里，有几条**在悬停 / 选中态会拿到 `border-color`**
     （单声明不是"完整框"，本来就不在口径内——量出来免得被读成漏网）。
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
    full_border_entries, load_border_kinds, load_border_register, read_page, rules_of,
    strip_lead_comments,
)

OUT = HERE / "probe-03-register.txt"
# 状态后缀：`:hover` / `.active` / `.on` …（本条量具只认"挂在同一个选择器后面的状态"这一形态）
STATE_TAIL_RE = re.compile(r"^(?::|\.(?:active|on|sel|current|checked|open|hover)\b|\[aria-)")


def main() -> int:
    kinds = load_border_kinds()
    register = load_border_register()
    page = read_page()  # 单一出处：口径模块自己那份读法（别在这里另拼路径 + read_text）
    disk = full_border_entries(page)

    reg_keys = {(s, sel) for s, sel, _k in register}
    disk_keys = {(e["scope"], e["sel"]) for e in disk}
    kind_ids = {k for k, _why in kinds}
    reg_by_key = {(s, sel): k for s, sel, k in register}
    disk_by_key = {(e["scope"], e["sel"]): e for e in disk}

    lines: list[str] = []
    add = lines.append
    add("# 读数：描边守卫轮 · 登记簿 ↔ 盘上双向对账")
    add("# 命令：python .scratch/border-guard/probe-03-register.py")
    add("# 口径：scope_lib.full_border_entries（站在 full_borders 上）；登记簿从守卫源码解析")
    add(f"# 时间：{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}")
    add("")
    add(f"盘上整圈完整框：{len(disk)} 条")
    add(f"登记簿登记项　：{len(register)} 条")
    add(f"双向差　　　　：盘上未登记 {len(disk_keys - reg_keys)} 条 / 登记项过期 {len(reg_keys - disk_keys)} 条")
    for key in sorted(disk_keys - reg_keys):
        e = disk_by_key[key]
        add(f"  [未登记] 第 {e['line']} 行 [{key[0]}] {key[1]} → {e['value']}")
    for key in sorted(reg_keys - disk_keys):
        add(f"  [过期]   [{key[0]}] {key[1]}（登记为 {reg_by_key[key]}）")

    dist = collections.Counter(k for _s, _sel, k in register)
    add("")
    add("## 每类条数（类别表形状）")
    for kid, why in kinds:
        add(f"  {kid:12s} {dist.get(kid, 0):3d}   {why}")
    for kid in sorted(set(dist) - kind_ids):
        add(f"  ⚠ 未定义的类别：{kid}（{dist[kid]} 条）")
    for kid in sorted(kind_ids - set(dist)):
        add(f"  ⚠ 空类别：{kid}")

    vis = sum(n for k, n in dist.items() if k not in ("placeholder", "nonbox"))
    nonbox = dist.get("placeholder", 0) + dist.get("nonbox", 0)
    add("")
    add("## 口径分列（别混着读）")
    add(f"  {len(register)} 条完整框 = **{vis} 条可见框** + **{nonbox} 条非框**"
        f"（{dist.get('placeholder', 0)} placeholder + {dist.get('nonbox', 0)} nonbox）")
    add("  「整圈完整框 N」是**声明数**口径（样式规则里的完整 border: 声明），")
    add("  与「渲染出来的框元素数」不是同一把尺（local-environment 记过这条）。")

    # ④ 脚注：placeholder 在状态态里拿到 border-color 的有几条
    all_rules = [(ln, " ".join(strip_lead_comments(sel).split()), page[b0:b1])
                 for ln, sel, b0, b1 in rules_of(page)]
    add("")
    add("## 脚注：非框那 21 条里，有几条在状态态里会拿到框（单声明不在口径内）")
    add("（扫描面 = placeholder + nonbox 全部 21 条——第一版只扫了 12 条 placeholder，")
    add("  双轴评审点名「覆盖面只有一半」；nonbox 9 条实测 0 条有状态上色，结论不变但扫描面得铺满。）")
    hit_total = 0
    scanned = 0
    for _s, sel, k in register:
        if k not in ("placeholder", "nonbox"):
            continue
        scanned += 1
        hits = [ln for ln, rsel, body in all_rules
                if rsel.startswith(sel) and STATE_TAIL_RE.match(rsel[len(sel):] or " ")
                and re.search(r"border(-color)?\s*:", body)]
        if hits:
            hit_total += 1
            add(f"  {k:12s} {sel:46s} → 状态规则 {len(hits)} 条（行 {', '.join(str(h) for h in hits[:6])}）")
    add(f"  合计：{scanned} 条非框里 **{hit_total} 条**在悬停 / 选中态会拿到 `border-color`")
    add("  → 那是「一屏一层」的合法逃逸（选中态本来就该有框），**不是漏网**：")
    add("    `border-color` 是单声明、不是完整框，本来就不在 `full_borders` 口径里。")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for line in lines:
        if line and not line.startswith("#"):
            print(line)
    print(f"\n已落盘：{OUT.relative_to(ROOT).as_posix()}")
    return 1 if (disk_keys - reg_keys) or (reg_keys - disk_keys) else 0


if __name__ == "__main__":
    raise SystemExit(main())
