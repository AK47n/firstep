#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""index.html 装载清单探针（feature: frontend-import-fossils，工单 01）。

只读。用途：
  1) plan   —— 算出宿主 <script type="module"> 里每条 import 的处置方案
                （删整条 / 转裸 import / 只删名字 / 保留）
  2) check  —— 复核不变量：每个具名导入都在宿主正文里被引用

解析口径（与 tests/js/static-import-guard.test.mjs、tests/js/import-usage-guard.test.mjs 对齐）：
  - import 语句 = `import { ... } from "..."` 或 `import "..."`（可跨多行）
  - 宿主正文 = 去掉 import 语句与 // 注释行之后剩下的代码
  - 「被引用」= 正文里出现该标识符（按 JS 标识符边界判定，见 ident_re）

用法：
    python .scratch/frontend-import-fossils/probe-imports.py plan
    python .scratch/frontend-import-fossils/probe-imports.py check
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HTML = REPO / "src" / "contest_generator" / "static" / "index.html"

IMPORT_RE = re.compile(
    r'^\s*import\s*(?:\{([^}]*)\}\s*from\s*)?["\']([^"\']+)["\']',
    re.M,
)


def ident_re(name: str) -> re.Pattern:
    """标识符引用判据。

    **不能用 `\\b`**：`$` 不是 word 字符，`\\b$\\b` 恒假——会把真正在用的 `$`
    （app.js 的 getElementById 别名，宿主 startup 里 `$("problem").focus()` 就在用）
    误判成未使用。工单 01 实测踩到（两个独立解析器都判错，删了就是启动即 ReferenceError）。
    """
    return re.compile(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])")


def split_host(text: str) -> tuple[str, str]:
    """切出宿主脚本块：返回 (脚本文本, 标记部分)。

    **必须截到 `</script>`**（工单 01 评审整改）：早先返回 `text[i:]`（一直到文件尾），
    把脚本之后的标记也算进"正文"，于是 `<div id="toast-root">` 把 `toast` 骗成"在用"
    ——同一份 HEAD 上探针报 258、守卫报 259，两套判据不同源。
    判据单源 = `tests/js/import-usage-guard.test.mjs` 的 `unusedImports`；本探针只是它的
    Python 镜像，口径必须逐字对齐（脚本块 + 去掉 import 语句与整行注释）。
    """
    marker = '<script type="module">'
    i = text.index(marker)
    j = text.index("</script>", i)
    return text[i:j], text[:i]


def parse_imports(host: str) -> list[dict]:
    """逐条解析 import 语句（含多行具名清单），返回带原始文本跨度的记录。"""
    out = []
    for m in IMPORT_RE.finditer(host):
        raw = m.group(0)
        names = []
        if m.group(1) is not None:
            for part in m.group(1).split(","):
                name = part.strip().split(" as ")[0].strip()
                if name:
                    names.append(name)
        out.append({
            "raw": raw,
            "spec": m.group(2),
            "names": names,
            "start": m.start(),
            "end": m.end(),
        })
    return out


def body_without_imports(host: str, imports: list[dict]) -> str:
    """去掉 import 语句与整行注释后的正文。"""
    chars = list(host)
    for imp in imports:
        for i in range(imp["start"], imp["end"]):
            chars[i] = " "
    stripped = "".join(chars)
    return "\n".join(l for l in stripped.splitlines() if not l.strip().startswith("//"))


def plan() -> int:
    text = HTML.read_text(encoding="utf-8")
    host, _markup = split_host(text)
    imports = parse_imports(host)
    body = body_without_imports(host, imports)

    delete_stmt, to_bare, trim, keep = [], [], [], []
    for imp in imports:
        used = [n for n in imp["names"] if ident_re(n).search(body)]
        dead = [n for n in imp["names"] if n not in used]
        if not imp["names"]:
            keep.append((imp, "已是裸 import"))
        elif not used:
            if imp["spec"].startswith("/js/fx/"):
                delete_stmt.append((imp, dead))
            else:
                to_bare.append((imp, dead))
        elif dead:
            trim.append((imp, dead, used))
        else:
            keep.append((imp, "全部在用"))

    total_names = sum(len(i["names"]) for i in imports)
    dead_names = (sum(len(d) for _, d in delete_stmt)
                  + sum(len(d) for _, d in to_bare)
                  + sum(len(d) for _, d, _ in trim))
    print(f"import 语句 {len(imports)} 条 / 具名 {total_names} 个")
    print(f"  删整条（纯 fx 域，全未引用） : {len(delete_stmt):2d} 条，带 {sum(len(d) for _, d in delete_stmt)} 个名字")
    print(f"  转裸 import（有顶层副作用）  : {len(to_bare):2d} 条，带 {sum(len(d) for _, d in to_bare)} 个名字")
    print(f"  只删名字（部分在用）         : {len(trim):2d} 条，删 {sum(len(d) for _, d, _ in trim)} 个名字")
    print(f"  原样保留                     : {len(keep):2d} 条")
    print(f"未引用名字合计 {dead_names} / {total_names}")
    if dead_names == 0:
        print("\n（已是干净态：装载清单里没有用不到的名字）")
        return 0
    print()
    for title, rows in (("== 删整条 ==", delete_stmt), ("== 转裸 import ==", to_bare)):
        print(title)
        for imp, dead in rows:
            print(f"  {imp['spec']:38s} ({len(dead)} 个名字全未引用)")
    print("== 只删名字 ==")
    for imp, dead, used in trim:
        print(f"  {imp['spec']:38s} 删 {len(dead):2d}，留 {len(used):2d}")
    return 0


def check() -> int:
    text = HTML.read_text(encoding="utf-8")
    host, _markup = split_host(text)
    imports = parse_imports(host)
    body = body_without_imports(host, imports)

    problems = []
    for imp in imports:
        if not imp["names"]:
            continue  # 裸 import：合法（副作用装载）
        unused = [n for n in imp["names"] if not ident_re(n).search(body)]
        if unused:
            problems.append(f"{imp['spec']} 导入了未使用的名字: {', '.join(unused)}")

    named = sum(1 for i in imports if i["names"])
    bare = sum(1 for i in imports if not i["names"])
    print(f"import 语句 {len(imports)} 条（具名 {named} / 裸 {bare}）；未使用名字问题 {len(problems)} 处")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    sys.exit(plan() if mode == "plan" else check())
