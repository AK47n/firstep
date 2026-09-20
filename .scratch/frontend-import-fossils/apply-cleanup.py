#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 plan 重写 index.html 的装载清单（feature: frontend-import-fossils，工单 01）。

安全前提（脚本自己验，不满足就 abort）：
  A. 每个待删名字在**整份 index.html**里，除它自己那条 import 语句之外**零出现**
     （不是"正文里零出现"——是整份文件零出现；出现即打印出来人工看）
  B. 待删的 fx 模块零顶层副作用（纯函数，删掉 HTML 这条装载不改变任何行为）
  C. 待删的 ui 模块必须是"靠被加载才接线"的那些 → 转裸 import，不删装载

处置：
  - 纯 fx 整条未用 → 删该 import 语句（保留其行尾注释）
  - ui 整条未用     → 改 `import "<spec>";`（保留行尾注释）
  - 部分在用        → 只把未用的名字从具名清单里去掉
  - 其余            → 一字不动

用法：
    python .scratch/frontend-import-fossils/apply-cleanup.py --dry-run
    python .scratch/frontend-import-fossils/apply-cleanup.py --apply
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HTML = REPO / "src" / "contest_generator" / "static" / "index.html"

# 单行具名 import：`import { a, b as c } from "/js/x.js";  // 备注`
NAMED_LINE = re.compile(
    r'^(?P<indent>[ \t]*)import[ \t]*\{(?P<names>[^}]*)\}[ \t]*from[ \t]*'
    r'(?P<quote>["\'])(?P<spec>[^"\']+)(?P=quote)[ \t]*;?(?P<tail>.*)$'
)
BARE_LINE = re.compile(r'^[ \t]*import[ \t]*["\'][^"\']+["\'][ \t]*;?')


def split_lines(text: str) -> tuple[str, str]:
    marker = '<script type="module">'
    i = text.index(marker)
    j = text.index("</script>", i)
    return text[:i], text[i:j]


def ident_re(name: str) -> re.Pattern:
    """标识符引用判据。

    不能用 `\\b`：`$` 不是 word 字符，`\\b$\\b` 恒假——会把真正在用的 `$`
    （app.js 的 getElementById 别名，宿主 startup 里 `$("problem").focus()` 就在用）
    误判成未使用。工单 01 实测踩到，两个独立解析器都判错。
    """
    return re.compile(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])")


def head_script(text: str, markup: str) -> str:
    """标记里那些**非 module** 的内联 <script> 内容（主题防闪烁）。"""
    out = []
    for m in re.finditer(r"<script(?![^>]*type=\"module\")[^>]*>(.*?)</script>", markup, re.S):
        out.append(m.group(1))
    return "\n".join(out)


def body_text(script: str) -> str:
    """宿主正文：去掉具名 import 语句与整行注释。"""
    keep = []
    for line in script.splitlines():
        if NAMED_LINE.match(line):
            continue
        if BARE_LINE.match(line):
            continue
        if line.strip().startswith("//"):
            continue
        keep.append(line)
    return "\n".join(keep)


def code_reference_lines(text: str, markup: str, script: str, name: str, stmt_line: str) -> list[tuple[int, str]]:
    """名字在**代码里**的引用位置（排除 import 语句自己与注释行）。

    只有两处 JS 能引用导入的名字：① module 脚本正文；② 标记里的内联非 module 脚本
    （主题防闪烁）。CSS 类名（`.toast-*`）、标记属性（`aria-expanded`）、脚本之后的
    DOM 标记（`<div id="toast-root">`）、迁移墓碑注释（`已迁至 … libFilterModules /`）
    都是同词碰撞，不算引用——判据只能看代码区。
    """
    pat = ident_re(name)
    hits = []
    for no, line in enumerate(script.splitlines(), 1):
        if not pat.search(line):
            continue
        if line == stmt_line:                       # 它自己那条 import
            continue
        if line.strip().startswith("//"):           # 行注释
            continue
        if BARE_LINE.match(line) or NAMED_LINE.match(line):
            continue                                # 别的 import 语句
        hits.append((no, line.strip()))
    for no, line in enumerate(head_script(text, markup).splitlines(), 1):
        if pat.search(line):
            hits.append((-no, "内联主题脚本: " + line.strip()))
    return hits


def strip_strings_and_comments(text: str) -> str:
    """把字符串 / 模板串 / 注释的内容换成空格（保留换行）。

    必须先剥：多行模板串的续行会落在列 0，不剥就会被当成"顶层可执行语句"
    （实测把 22 个纯 fx 模块全误判成有副作用）。
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            out.append("  ")
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
        elif c in "\"'`":
            quote = c
            out.append(" ")
            i += 1
            while i < n:
                if text[i] == "\\":
                    out.append("  ")
                    i += 2
                    continue
                if text[i] == quote:
                    break
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append(" ")
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def has_toplevel_side_effects(rel_spec: str) -> bool:
    """模块被加载时是否执行**页面依赖的**副作用（DOM 接线 / 首帧 DOM 写）。

    判据：剥掉字符串与注释后，列 0 的可执行语句——但**排除探针桥**
    （`if (typeof window !== "undefined") Object.assign(window, {...})`）：
    那类语句是给 CDP 探针 / 浏览器用例调纯函数用的，而且模块本身会被它的 ui
    消费者加载（本工单已验证 22 个 fx 全部仍被模块图引用），所以它不是"装载必须保留"的理由。

    这条决定"整条删"还是"转裸 import"（工单 01 评审整改）：
      - 有页面依赖的副作用 → 装载本身有意义，必须保留（转裸 import 让意图显式）
      - 没有 → 装载纯冗余（其消费者自己 import），整条删
    原先只看目录（fx 删 / ui 转裸）是错的：`ui/progress.js` 是纯声明模块且被 6 个模块
    import，`ui/files.js` 只有常量声明——它们转裸 import 等于"保留了冗余装载"。
    """
    path = REPO / "src" / "contest_generator" / "static" / rel_spec.lstrip("/")
    stripped = strip_strings_and_comments(path.read_text(encoding="utf-8"))
    for line in stripped.split("\n"):
        if not line[:1].strip():            # 空行（或原为字符串/注释）
            continue
        if line[0].isspace():               # 缩进 = 在函数体 / 对象里
            continue
        if line.startswith("import "):
            continue
        if re.match(r"^if \(typeof (window|document)\b", line):
            continue                        # 探针桥（块体缩进，不影响判定）
        if re.match(r"^(export\s+)?(async\s+)?function\b", line):
            continue
        if re.match(r"^(export\s+)?(const|let|var)\s+[A-Za-z_$][\w$]*\s*=", line):
            continue
        if line.startswith(("}", ")", "]", "export {")):
            continue
        return True
    return False


def main(apply: bool) -> int:
    text = HTML.read_text(encoding="utf-8")
    markup, script = split_lines(text)
    body = body_text(script)

    lines = script.splitlines(keepends=True)   # 保留行尾：拼接用 ""，删行即整行进/出，末尾换行不丢
    plan_rows = []
    for idx, line in enumerate(lines):
        m = NAMED_LINE.match(line)
        if not m:
            continue
        names = [n.strip().split(" as ")[0].strip() for n in m.group("names").split(",") if n.strip()]
        spec = m.group("spec")
        used = [n for n in names if ident_re(n).search(body)]
        dead = [n for n in names if n not in used]
        if not dead:
            continue
        action = "trim" if used else ("bare" if has_toplevel_side_effects(spec) else "delete")

        # 前提 A：待删名字在**代码里**没有引用（注释 / CSS / 标记的同词碰撞不算）
        refs = {}
        for n in dead:
            hits = code_reference_lines(text, markup, script, n, line)
            if hits:
                refs[n] = hits
        plan_rows.append({
            "idx": idx, "spec": spec, "names": names, "used": used, "dead": dead,
            "action": action, "refs": refs, "tail": m.group("tail"),
            "indent": m.group("indent"),
        })

    print(f"待处置语句 {len(plan_rows)} 条 / 待删名字 "
          f"{sum(len(r['dead']) for r in plan_rows)} 个")
    by_action = {}
    for r in plan_rows:
        by_action.setdefault(r["action"], []).append(r)
    for action in ("delete", "bare", "trim"):
        rows = by_action.get(action, [])
        print(f"  {action:7s} {len(rows):2d} 条 / {sum(len(r['dead']) for r in rows):3d} 个名字")

    flagged = [r for r in plan_rows if r["refs"]]
    if flagged:
        print("\n✗ 这些待删名字在代码里仍有引用 —— 不许删（判据错了，停下来看）：")
        for r in flagged:
            for n, hits in r["refs"].items():
                for no, line in hits[:3]:
                    print(f"   [{r['spec']}] {n} @L{no}: {line[:120]}")
        return 3

    if not apply:
        print("\n（--dry-run：未写入。逐条明细见下）")
        for r in plan_rows:
            print(f"  {r['action']:7s} {r['spec']:36s} 删 {len(r['dead']):2d} 留 {len(r['used']):2d}")
        return 0

    # 前提 B：整条删的模块必须"删了不改变行为"——有顶层副作用的一律改走裸 import
    for r in plan_rows:
        if r["action"] != "delete":
            continue
        if has_toplevel_side_effects(r["spec"]):
            print(f"✗ {r['spec']} 有顶层副作用，不能整条删（应转裸 import）")
            return 2

    for r in plan_rows:
        i = r["idx"]
        line = lines[i]
        eol = line[len(line.rstrip("\r\n")):]      # 保留原行尾（LF/CRLF）——丢弃它会把 </script> 粘到代码尾
        if r["action"] == "delete":
            lines[i] = (r["tail"] + eol) if r["tail"].strip() else None
        elif r["action"] == "bare":
            lines[i] = f'{r["indent"]}import "{r["spec"]}";{r["tail"]}{eol}'
        else:
            lines[i] = (f'{r["indent"]}import {{ {", ".join(r["used"])} }} '
                        f'from "{r["spec"]}";{r["tail"]}{eol}')

    new_script = "".join(l for l in lines if l is not None)
    HTML.write_text(markup + new_script + text[len(markup) + len(script):], encoding="utf-8")
    print(f"\n✓ 已写入 {HTML.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
