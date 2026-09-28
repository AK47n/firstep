r"""工单 05 施工脚本（五）：**自查与双轴评审**抓到的整改。

形状照 04d：改锚点在**全文**里唯一命中；锚点没了但**新形态已在** ⇒ 记为"已应用"（**可重跑**）；
插入块与替换串里的换行按文件实际换行（CRLF）换算——04d 的教训（三引号块写下裸 LF）。
**本支是"apply-05d 之后再纠正它"的那一支**（同 04 单：04a 写出 `;m;`、04d 修回）：
`apply-05d` 的插入块保持**它当初写下的原形态**（单一出处），纠正一律在这里。

  A. **空告警块 + 成功态**（两轴都抓到，Standards 判为硬违规）：
     · `#settings-msg` **默认就是空 div + `class="error"`**（`index.html`），而
       `ui/settings.js` 保存前只清 `textContent`、不摘类 —— 05d 那条 `#tab-settings .error`
       于是让页面**一打开就挂着一条整宽淡红框**（评审实测 1358×18，到第一次保存成功才消失；
       本单自己入库的 `05-after-dark-settings-full.png` 底下那条就是它）。
     · 保存**成功**那一态同时带 `error ok` 两个类（成功路径只 `classList.add("ok")`）。
     → 选择器补 `:not(.ok):not(:empty)`（JS 一行不动，只好在 CSS 里认这两态），两态都写进注释。
  B. **不可逆动作的重量**（Spec (a)2）：`#btn-reset-records`（"清空本地记录"，旁边自述
     "清理不可撤销"）此前**没有 `danger` 类**，与"检查完整包"同重量 → 补上（只新增类名，
     id / DOM 顺序 / 既有类名语义都不动）。
  C. **分组带**（Spec (a)1）：票面要"分组靠大间距 + 分组标题表达"，而卡与卡之间仍只有
     `.card { margin-bottom: var(--space-5) }`、也没新增分组带类名。→ 照 **02 单
     `#tab-hwcheck .hwcheck-band` 的先例**（"只插入标题元素"）在 `#tab-settings` 里插 5 条
     `.settings-band`（应用与 AI / 库与工具链 / 模型与通道 / 体检与观测 / 更新与维护）+
     一条 CSS；DOM 顺序与既有 id 一个不动。
  D. **同一块面板里的死类**（README 坑 3；Spec 附注）：`fx/materials-update.js` 与
     `fx/full-update.js` 一直在渲染 `.warning`（弱网重试 / 整批将被移除），而**全站没有
     `.warning` 规则**——补一条最小样式（警示色文字，框留给"失败"那一档）；`.full-confirm`
     （确认弹窗内容壳，`.ref-files-modal` 已给形状）**不算死类**，这句记进票尾的账。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05e-review-fixups.py --dry-run
    $env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\apply-05e-review-fixups.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_lib import PAGE, ROOT, read_page, write_page  # noqa: E402

EOL = "\r\n"

# [(锚点（全文唯一）, 换成, 过后的"标记"（用于可重跑判定）, 理由)]
MODIFY: list[tuple[str, str, str, str]] = [
    ("     这里按页作用域给形状。配色照 `.hwcheck-warn` 那一类（描边用主色，不用淡色边框）。 */",
     """     这里按页作用域给形状。配色照 `.hwcheck-warn` 那一类（描边用主色，不用淡色边框）。
     ⚠ 两个 `:not(…)` 都是必需的——**读渲染方 + 看默认态**才知道：
       · `:not(.ok)`：`ui/settings.js` 保存成功时只 `classList.add("ok")`、**不摘 `error`**
         （`#settings-msg` 的初始类就是 error），不排除它就会把"已保存，立即生效。"装进红框；
       · `:not(:empty)`：`#settings-msg` **默认就是空 div + class="error"**，不排除它页面一打开
         就挂着一条整宽红框（评审实测 1358×18，到第一次保存成功才消失）。
     JS 一行不动，只好在 CSS 里认这两态。 */""",
     "两个 `:not(…)` 都是必需的",
     "A 空告警块 + 成功态：两种「不该画框」的态写进注释"),
    ("#tab-settings .error { background: var(--danger-dim);",
     "#tab-settings .error:not(.ok):not(:empty) { background: var(--danger-dim);",
     "#tab-settings .error:not(.ok):not(:empty) {",
     "A 同上：选择器认「有文字、且不是成功态」"),
    ('<button id="btn-reset-records" type="button" data-ico="trash">清空本地记录</button>',
     '<button id="btn-reset-records" type="button" class="danger" data-ico="trash">清空本地记录</button>',
     'id="btn-reset-records" type="button" class="danger"',
     "B 不可逆动作补 danger（清空本地记录 / 清理不可撤销）"),
]

# [(选择器片段（全文唯一）, 插在该规则 `}` 之后, 插入块, 过后的标记, 理由)]
INSERT_AFTER_RULE: list[tuple[str, str, str, str, str]] = [
    (".materials-progress .muted { color: var(--text); }",
     """  /* 弱网重试 / 整批移除的提示（`.warning`）：`fx/materials-update.js` 与
     `fx/full-update.js` 一直在渲染它，而全站**从来没有过** `.warning` 规则（死类，README 坑 3）
     ——补一条最小样式：语义提示那一档用警示色**文字**，框留给"失败"那一档。 */
  .update-result .warning, .materials-progress .warning { color: var(--warn); }""",
     ".warning { color: var(--warn); }",
     "D 同一块面板里的死类 `.warning` 补实"),
    (".settings-toolbar { display: flex; align-items: center; justify-content: space-between;",
     """  /* 设置页分组带（工单 ui-density-sitewide/05）：14 张卡读成五段——**只插入标题元素**，
     DOM 顺序与既有 id 一个不动（照 02 单 `#tab-hwcheck .hwcheck-band` 的先例）。
     标题 + 一条横线（`::after`）把"组"与"卡"两级分开；组间大间距 = 卡间距 20px + 这里 24px。
     （hwcheck 那条 `:first-child { margin-top: 0 }` 这里**不加**：本条带前面还有页首工具栏，
     永远不是第一个子元素——照抄就成了死规则，坑 5。） */
  .settings-band { display: flex; align-items: center; gap: var(--space-2);
    margin: var(--space-6) 0 var(--space-3); font-size: var(--fs-block);
    font-weight: 650; color: var(--text); }
  .settings-band::after { content: ""; flex: 1 1 auto; height: 1px; background: var(--border); }""",
     ".settings-band::after",
     "C 分组带的样式（与 `.hwcheck-band` 同形）"),
]

# [(DOM 那一行的原文, 插在它**前面**的块, 理由)]
INSERT_BEFORE_LINE: list[tuple[str, str, str]] = [
    ('    <div class="card" data-collapse-id="app">',
     '    <div class="settings-band">应用与 AI</div>' + EOL, "C 分组带①"),
    ('    <div class="card" data-collapse-id="libs">',
     '    <div class="settings-band">库与工具链</div>' + EOL, "C 分组带②"),
    ('    <div class="card" data-collapse-id="local-llm">',
     '    <div class="settings-band">模型与通道</div>' + EOL, "C 分组带③"),
    ('    <div class="card" data-collapse-id="env-check">',
     '    <div class="settings-band">体检与观测</div>' + EOL, "C 分组带④"),
    ('    <div class="card" data-collapse-id="software-update">',
     '    <div class="settings-band">更新与维护</div>' + EOL, "C 分组带⑤"),
]


def crlf(block: str) -> str:
    return block.replace("\r\n", "\n").replace("\n", EOL)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = read_page()
    edits: list[tuple[int, int, str, str]] = []
    problems: list[str] = []
    done: list[str] = []

    # ① 改口径（全文唯一锚点）
    for old, new, marker, why in MODIFY:
        if old not in text:
            if marker in text:
                done.append(f"已应用（{why}）")
            else:
                problems.append(f"锚点 {old[:60]!r}… 没命中，新形态也不在")
            continue
        if text.count(old) != 1:
            problems.append(f"锚点 {old[:60]!r}… 命中 {text.count(old)} 次（期望 1）")
            continue
        at = text.index(old)
        edits.append((at, at + len(old), crlf(new), why))

    # ② 插在规则 `}` 之后（CSS 块）
    for frag, block, marker, why in INSERT_AFTER_RULE:
        if marker in text:
            done.append(f"已应用（{why}）")
            continue
        hits = text.count(frag)
        if hits != 1:
            problems.append(f"插入锚点 {frag[:50]!r}… 命中 {hits} 次（期望 1）")
            continue
        close = text.index("}", text.index(frag) + len(frag)) + 1
        edits.append((close, close, EOL + crlf(block), why))

    # ③ 插在 DOM 那一行**之前**
    for line_text, block, why in INSERT_BEFORE_LINE:
        if block.strip() in text:
            done.append(f"已应用（{why}）")
            continue
        hits = text.count(line_text)
        if hits != 1:
            problems.append(f"DOM 锚点 {line_text.strip()[:50]!r} 命中 {hits} 次（期望 1）")
            continue
        at = text.index(line_text)
        edits.append((at, at, crlf(block), why))

    # ④ 编辑区间不许重叠（04 单的账第 9 条）
    for (s1, e1, n1, _), (s2, _, _, _) in zip(sorted(edits), sorted(edits)[1:]):
        if s2 < e1:
            problems.append(f"编辑区间重叠：[{s1},{e1}) {n1[:40]!r} 与 [{s2},…)")

    print(f"== 05 整改：{len(edits)} 处待改 / {len(done)} 处已应用 ==")
    for *_, note in sorted(edits, key=lambda e: e[0]):
        print("  改    " + note)
    for note in done:
        print("  跳过  " + note)

    if problems:
        print("\n== **停下**：以下对不上，一个字节都没写 ==")
        for p in problems:
            print("  ✗ " + p)
        return 1

    for start, end, new, _ in sorted(edits, key=lambda e: -e[0]):
        text = text[:start] + new + text[end:]

    if not args.write:
        print("\n（--dry-run：没有写盘；确认无误后加 --write）")
        return 0
    write_page(text)
    print(f"\n[已写盘] {PAGE.relative_to(ROOT)}；{len(edits)} 处 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
