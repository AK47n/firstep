r"""描边守卫轮 · 施工脚本（02 单）：渲染方（`static/js/**`）内联整圈框的登记簿。

**一次性脚本**（照 01 单 `generate-01-register.py` 的先例）：
**真源是守卫里那张 `JS_BORDER_REGISTER`**——本脚本与 `register-js-block.js.txt`
都是**已被消费的一次性产物，别拿它们当判据**。
带 **`--check`**：按盘上现算 + 本文件的 `REGISTER` 重新生成一遍，与守卫里那张表逐条比，
不一致就非零退出（复核用 `probe-04-js-register.py`——它从守卫源码读，不读本文件）。

它做两件事：
  1. **按盘上的真值**列出内联整圈框（口径见下），并**逐个验锚点**：
     每个锚点必须命中它该命中的那些行、且**不多不少**（锚点不独特 = 以后会误配）；
  2. 生成 `const JS_BORDER_REGISTER = [...]` 文本块。

**口径**：与样式块面差一处（内联样式写在 HTML 属性里，取值可能以 `"` 收尾）；
两种拼法都认；`DEAD_BORDER` 两边共用——**全部从 `scope_lib` import，本脚本不另抄一份**
（01 单双轴评审点过"公共件不 import"这毛病，02 不许重演）。
"""

from __future__ import annotations

import collections
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "ui-density-sitewide"))

from scope_lib import (  # noqa: E402
    DEAD_BORDER, JS_BORDER_LINE_RE, js_files, load_js_border_register,
)

OUT = HERE / "register-js-block.js.txt"
CHECK = "--check" in sys.argv

HEADER = [
    "  // ⚠ 本表由 `.scratch/border-guard/generate-02-js-register.py` 生成过一次"
    "（`--check` 可复核生成关系）；",
    "  //   **真源就是这张表本身**——那个脚本与 `register-js-block.js.txt` 是已消费的一次性产物，"
    "别拿它们当判据。",
    "  // ⚠ 同一条锚点登记两次 = 盘上真有两条逐字相同的行（`.role-type` 那条）；"
    "锚点是**该行的一段可认片段**，不是行号。",
]

# 登记项：(文件, 锚点, 类别)。**锚点是该行的一段可认片段**（不取行号——行号会随插行漂）。
# 同一锚点登记多次 = 盘上真有多条逐字相同的行（`.role-type` 那条就是）。
REGISTER: list[tuple[str, str, str]] = [
    ("fx/flash.js", 'style="border:1px solid var(--warn);', "alert"),
    ("fx/task.js", "border:1px solid var(--border);border-radius:var(--radius-md);background:var(--panel-2)", "alert"),
    ("ui/codeeditor.js", "border:1px solid #888", "float"),
    ("ui/generate-recommend.js", "border:1px solid var(--border,#ccc)", "doc"),
    ("ui/generate-recommend.js", 'class="warn-box" style="border:1px solid var(--border)"', "alert"),
    ("ui/generate-pins.js", "background:var(--pin-pad);border:1px solid var(--border-strong)", "nonbox"),
    ("ui/generate-pins.js", 'border:1px dashed var(--warn)"', "nonbox"),
    ("ui/generate-pins.js", 'background:var(--pin-fixed-pad);border:1px solid var(--border)"', "nonbox"),
    ("ui/generate-pins.js", 'class="role-type" style="color:${st[0]};background:${st[1]};border:1px solid ${st[0]}"', "tag"),
    ("ui/generate-pins.js", 'class="role-type" style="color:${st[0]};background:${st[1]};border:1px solid ${st[0]}"', "tag"),
]


def disk_entries() -> list[tuple[str, int, str, str]]:
    """盘上的内联整圈框——**口径从 scope_lib import**（`JS_BORDER_LINE_RE` / `DEAD_BORDER`），
    本脚本不另抄一份（01 单双轴评审点的"公共件不 import"）。"""
    out = []
    for rel, text in js_files():
        for i, line in enumerate(text.split("\n"), start=1):
            for m in JS_BORDER_LINE_RE.finditer(line):
                value = (m.group(1) or m.group(2) or "").strip()
                if not value or value.split()[0] in DEAD_BORDER:
                    continue
                out.append((rel, i, line, value))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    disk = disk_entries()
    print(f"盘上渲染方内联整圈框：{len(disk)} 处")
    for rel, line, _raw, value in disk:
        print(f"  {rel}:{line}  →  {value}")

    # 每个「锚点」该命中几条（同一锚点登记几次，就该命中几行）
    want = collections.Counter((f, a) for f, a, _k in REGISTER)
    got: collections.Counter[tuple[str, str]] = collections.Counter()
    unmatched = []
    for rel, line, raw, value in disk:
        hits = {key for key in want if key[0] == rel and key[1] in raw}
        if len(hits) != 1:
            unmatched.append((rel, line, value, sorted(hits)))
            continue
        got[next(iter(hits))] += 1
    if unmatched:
        print("\n锚点不独特 / 没配对上的行（停手）：")
        for rel, line, value, hits in unmatched:
            print(f"  {rel}:{line}  {value}  命中 {hits}")
        return 1
    diff = {k: (want[k], got.get(k, 0)) for k in set(want) | set(got) if want[k] != got.get(k, 0)}
    if diff:
        print("\n登记条数与盘上条数不等（停手）：")
        for (f, a), (w, g) in diff.items():
            print(f"  {f} / {a[:60]}…  登记 {w} 条，盘上 {g} 条")
        return 1
    if len(REGISTER) != len(disk):
        print(f"\n登记 {len(REGISTER)} 条 ≠ 盘上 {len(disk)} 条（停手）")
        return 1

    lines = ["const JS_BORDER_REGISTER = [", *HEADER]
    written: list[tuple[str, str, str]] = []
    for file, anchor, kind in REGISTER:
        lines.append(f'  ["{file}", \'{anchor}\', "{kind}"],')
        written.append((file, anchor, kind))
    lines.append("];")
    dist = collections.Counter(k for _f, _a, k in REGISTER)

    if CHECK:
        # `--check`：守卫里那张表必须与本脚本**写出去的**那份逐条相同（含顺序）
        in_guard = load_js_border_register()
        if in_guard == written:
            print(f"[OK] 守卫里的渲染方登记簿与本脚本生成结果逐条相同（{len(written)} 条，含顺序）")
            return 0
        print(f"[DIFF] 守卫 {len(in_guard)} 条 vs 生成 {len(written)} 条")
        for i, (a, b) in enumerate(zip(in_guard, written)):
            if a != b:
                print(f"  首个不同在第 {i + 1} 条：守卫 {a} / 生成 {b}")
                break
        for row in [r for r in written if r not in in_guard][:10]:
            print(f"  只在生成里：{row}")
        for row in [r for r in in_guard if r not in written][:10]:
            print(f"  只在守卫里：{row}")
        return 1

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    print("\n锚点全部独特、条数逐条对上 ✅  类别分布：" + " / ".join(f"{k} {dist[k]}" for k in sorted(dist)))
    print(f"守卫表已生成：{OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
