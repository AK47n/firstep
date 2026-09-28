r"""工单 05 施工脚本（四）：**新增规则与两处口径改动**（字号 / 间距 / 描边之外的那部分）。

这一支动的都不是"换个令牌"，而是本单验收里那三条**观感**要求——全部纯 CSS，**一行 JS 不动**
（`static/js/**` 零字节；渲染方给的类名已经在，比如 `.update-result` 早就渲染出来了、只是从来没样式）：

  A. **环境体检：三档重量分明**（验收「检查项成组呈现（通过 / 缺失 / 警告三种重量分明）」）
     —— 通过 = 安静（只有绿徽章）、警告 = 徽章、**失败 = 整行淡红底 + 左条**。
     用 `:has()` 认失败行（老浏览器不支持时整条忽略，纯增强）——先例 `#tab-hwcheck .card:has(…)`；
     左条用 `box-shadow: inset`，**不留布局位移**（`border-left` 会把内容推 3px，行与行就不齐了）。
  B. **更新 / 下载结果块**（验收「更新面板可读：版本号、体量、进度三处信息的主次分明，
     数值优先于标签」）—— `.update-result` 与 `.materials-progress` 之前**一条样式都没有**
     （渲染方 `fx/update.js` / `fx/full-update.js` / `fx/materials-update.js` 早就输出这个类名），
     现在给它们淡底块 + 正文档字号；`<b>` 里的**数值**抬到 `--fs-block` + accent（标签留在 13/14），
     进度里那行"体量 / 速度 / 剩余"用正文色（不再是 muted）。
  C. **失败提示 = 语义告警块**（验收「更新失败的提示是『语义告警块』那一类，保留它那一条描边」）
     —— 按页作用域 `#tab-settings .error` 给形状；**全局 `.error` 不动**（别处是行内红字）。
  D. **卡内小节标题不再是灰字**（验收「分组靠大间距 + 分组标题表达」）—— 字号在 05a 里升到
     `--fs-block`，这里把配色从 muted 改成正文色（口径 = 03 单立的"小节标题（正文色 + 加粗，
     不是灰字）"）；可点的折叠头（"计费 ▾"）跟着走正文色，悬停转 accent 的可点提示照旧
     （票面备注写着"折叠行为不变，**只改折叠头的样子**"）。

完整性证明：每条插入锚点都断言"恰好命中一条规则"；插入块按文件实际换行（`\r\n`）；
改完复扫：**该作用域裸字号 / 裸令牌间距仍为 0**（新规则里不许再引入裸 px）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05d-new-rules.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05d-new-rules.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import (PAGE, ROOT, bare_fonts, bare_token_spaces, load_scopes,  # noqa: E402
                       read_page, rules_of, scope_of, write_page)

SCOPE = "settings"
EOL = "\r\n"

# 行号（探针口径）→ (选择器片段, 插在它后面, 插入块, 理由)
INSERT: dict[int, tuple[str, str, str]] = {
    363: (".env-row:last-child",
          """  /* 体检行的三档重量（工单 ui-density-sitewide/05）：通过 = 安静（只有绿徽章）、
     警告 = 徽章、**失败 = 整行淡红底 + 左条**——"哪几条要动手"一眼可见。
     `:has()` 老浏览器不支持时整条忽略（页面照旧可用，只是不安静），先例 = `#tab-hwcheck .card:has(…)`；
     左条走 `box-shadow: inset` 而**不是** `border-left`——后者会把这一行的内容推 3px，行与行就不齐了。 */
  .env-row:has(.env-badge.env-err) { background: var(--danger-dim);
    box-shadow: inset 3px 0 0 var(--danger); border-radius: var(--radius-xs); }""",
          "A 体检失败行加重量"),
    1528: (".materials-part-row",
           """  /* 更新 / 下载结果块（工单 ui-density-sitewide/05）：三处信息的主次——
     **版本号抬到 --fs-block + accent、体量跟着整块从 muted 13 提到正文色 14**（`<b>` 之外的数字
     在渲染方是裸文本节点：`fx/update.js` 的"更新包约 12 MB"CSS 够不着——不动 JS，如实记账；
     `fx/full-update.js` 的体量在 `<b>` 里，走同一条规则）；整块走淡底、不画框（一屏一层）。
     `color: var(--text)` 是必需的：容器 `#update-results` 带 `.muted`，不覆盖整块就一直是灰的。 */
  .update-result, .materials-progress { background: var(--panel-2); border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4); margin-top: var(--space-2); font-size: var(--fs-body);
    line-height: 1.7; color: var(--text); }
  .update-result b { font-size: var(--fs-block); color: var(--accent); }
  .materials-progress .muted { color: var(--text); }""",
           "B 更新/进度结果块"),
    1602: (".settings-stickybar",
           """  /* 设置页的失败提示（工单 ui-density-sitewide/05）：更新 / 资料库 / 保存失败都是
     **语义告警块**（例外①：保留它那一条描边）——全局 `.error` 不动（别处是行内红字），
     这里按页作用域给形状。配色照 `.hwcheck-warn` 那一类（描边用主色，不用淡色边框）。 */
  #tab-settings .error { background: var(--danger-dim); border: 1px solid var(--danger);
    border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }""",
           "C 失败提示的告警块形状"),
}

# 行号（探针口径）→ (选择器片段, 锚点, 换成, 理由)
MODIFY: dict[int, tuple[str, str, str, str]] = {
    1584: (".settings-section", "color: var(--muted);", "color: var(--text);",
           "D 卡内小节标题不再是灰字（字号已在 05a 升到 --fs-block）"),
    1588: (".settings-collapse-head", "color: var(--muted);", "color: var(--text);",
           "D 可点折叠头随它所在的小节标题走正文色（悬停转 accent 照旧）"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    scopes = load_scopes()
    problems: list[str] = []
    edits: list[tuple[int, int, str, str]] = []

    # ① 插入点：找到那条规则，插在它的 `}` 之后
    hit_ins: dict[tuple[int, str], int] = {}
    for line, sel, b0, b1 in rules_of(text):
        if line not in INSERT:
            continue
        frag, block, why = INSERT[line]
        if frag not in sel:
            continue
        hit_ins[(line, frag)] = hit_ins.get((line, frag), 0) + 1
        close = text.index("}", b1) + 1
        # ⚠ 插入块里的换行一律换算成文件实际换行（CRLF）——02 单那条坑的**插入版**：
        #   三引号字符串里的是裸 LF，直接拼进去就又是一批裸 LF（本支第一版实测 16 处，
        #   `fix-crlf.py` 当场报出来）。匹配侧与替换侧都要按文件实际换行走。
        block_crlf = block.replace("\r\n", "\n").replace("\n", EOL)
        edits.append((close, close, EOL + block_crlf, f"L{line}  插在 {frag} 之后  → {why}"))
    for line, (frag, _, _) in sorted(INSERT.items()):
        if hit_ins.get((line, frag), 0) != 1:
            problems.append(f"L{line}（{frag}）的插入锚点命中 {hit_ins.get((line, frag), 0)} 条（期望 1）")

    # ② 改口径：按 (行号, 选择器片段) 认人，锚点在规则体内恰好命中一次
    hit_mod: dict[tuple[int, str], int] = {}
    for line, sel, b0, b1 in rules_of(text):
        if line not in MODIFY:
            continue
        frag, old, new, why = MODIFY[line]
        if frag not in sel:
            continue
        body = text[b0:b1]
        hit_mod[(line, old)] = hit_mod.get((line, old), 0) + 1
        if body.count(old) != 1:
            problems.append(f"L{line}（{frag}）: 锚点 {old!r} 出现 {body.count(old)} 次（期望 1）")
            continue
        at = b0 + body.index(old)
        edits.append((at, at + len(old), new, f"L{line}  {frag}  {old} → {new}  （{why}）"))
    for line, (frag, old, _, _) in sorted(MODIFY.items()):
        if hit_mod.get((line, old), 0) != 1:
            problems.append(f"L{line}（{frag}）的锚点 {old!r} 命中 {hit_mod.get((line, old), 0)} 次（期望 1）")

    # ③ 编辑区间不许重叠（04 单的账第 9 条）
    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1[:40]!r} 与 [{s2},…)")

    print(f"== {SCOPE} 新增 / 改口径：{len(edits)} 处 ==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  " + note)
    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    # ④ 复扫：新规则里不许再引入裸 px（字号 / 令牌间距两条腿仍要绿）
    left_f = bare_fonts(text, SCOPE)
    left_s = bare_token_spaces(text, SCOPE)
    if left_f or left_s:
        print("\n== **停下**：新规则把裸值带回来了（没写盘）==")
        for line, value in sorted(left_f):
            print(f"  ✗ 字号 L{line}: {value}px")
        for line, sel, value in left_s:
            print(f"  ✗ 间距 L{line} {sel[:60]} → {value}px")
        return 1

    if not args.write:
        print(f"\n（--dry-run：没有写盘。复扫 {SCOPE} 裸字号 / 裸令牌间距 = 0 ✅；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}：插入 {len(INSERT)} 条规则 + 改 {len(MODIFY)} 处口径 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
