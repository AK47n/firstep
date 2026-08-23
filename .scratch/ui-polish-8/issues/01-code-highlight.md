# 工单 01：main.c 行号 + 语法着色

- Status: resolved
- 依赖：无

## 目标

main.c 预览区（`<textarea id="main-c">`，L825，rows=16 可编辑）加行号列与
C 语法着色，观感向 IDE 靠拢。可编辑性不变（仍是 textarea）。

## 实现

1. HTML：把 textarea 包进 `.code-wrap`，前置行号层与高亮层：
   ```html
   <div class="code-wrap">
     <div id="main-c-nums" class="line-nums" aria-hidden="true"></div>
     <pre id="main-c-hl" class="hl-layer" aria-hidden="true"></pre>
     <textarea id="main-c" rows="16" ...></textarea>
   </div>
   ```
   （textarea 保留原 id/属性，其余 JS 引用不变。）
2. textarea 样式：背景透明、文字 `color: transparent`、`caret-color: var(--accent)`、
   同字体同 padding（与 pre 完全对齐）；pre 层 `pointer-events:none`、绝对定位铺满。
3. 滚动同步：textarea `scroll` 事件把 `scrollTop/scrollLeft` 同步给 nums/hl 两层的
   父级（pre 直接滚动；nums 用 transform translateY 或独立 scrollTop）。
4. 纯函数（tests/js 可抽取、自包含、不引用模块级常量）：
   - `cHighlight(code)` → HTML 字符串。先 `esc`（`&<>"'`）再按序包 token：
     行注释 `//…`、块注释 `/*…*/`、字符串 `"…"` `'…'`、预处理 `#…`（行首）、
     关键字词表、数字。span class：`tok-com` / `tok-str` / `tok-pre` /
     `tok-kw` / `tok-num`。
   - `cLineCount(code)` → 行号数组 join 的字符串（至少 1 行）。
5. 刷新时机：`syncMainCHighlight()`（读 textarea 值 → 写两层），调用点：
   `input` 事件、生成骨架成功（`$("main-c").value = data.main_c` 处，L3040 附近）、
   草稿恢复（L6065 `if (d.mainC) { $("main-c").value = d.mainC; ... }` 处）。
6. CSS：token 配色（深色）：注释 `#3fb950`（绿）、字符串 `#d29922`（琥珀）、
   预处理 `#8b949e`（灰）、关键字 `#00d4ff`（青）、数字 `#bc8cff`（紫）；
   亮色主题对应覆盖（注释 `#1a7f37`、字符串 `#9a6700`、预处理 `#59636e`、
   关键字 `#0096c7`、数字 `#8250df`）。行号 muted、右对齐、等宽。
   prefers-reduced-motion 不涉及（无动画）。

## 测试

- tests/js/code-highlight.test.mjs：
  - cHighlight 注释/字符串/关键字/数字/预处理各 1 例 + 转义（`<` `&`）1 例 +
    空串 + 混合行；
  - cLineCount：空串=1 行、3 行文本=3、结尾换行不产生多余行号。
- 契约测试不受影响（无 DOM 结构钉依赖 main-c 的直接父级）。

## 验收

行号随内容变化；滚动三同步；输入/生成/恢复都刷新；光标正常；截图目检。
