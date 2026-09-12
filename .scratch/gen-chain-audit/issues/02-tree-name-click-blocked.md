# 02 — 修：文件树「点文件名打不开文件」（行操作区浮层吃掉指针）

**要做什么：** 代码栏左侧文件树里，hover 一行之后**点文件名必须真的打开它**；
行右的 `✎ 重命名` / `🗑 删除` 仍然可点，但**不许压在文件名按钮的点击区上**。

**被谁阻塞：** 无。

**状态：** resolved

- [x] **真机复现（现成）**：审计脚本 Y 节 —— `page.locator(...).hover()` 直接
      **超时**，playwright 的报错就是证据：
      `<button title="重命名" … aria-label="重命名 main.c">✎</button> from
      <span class="code-tree-actions">…</span> subtree intercepts pointer events`。
      独立复现脚本 `tests/browser/probe-tree-hit.mjs` 把几何量出来（行滚进视口后
      逐 15px 横扫 `elementFromPoint`）：

      | 量 | 修前实测 |
      |----|----------|
      | 文件名按钮 | 225 × 25 |
      | 按钮正中央（playwright hover 的落点）命中 | `BUTTON.code-tree-act`（✎ 重命名） |
      | 行操作区容器 | x=108、**w=131**、h=24 —— 横向覆盖行宽 **58%** |
      | 可点区 | 只剩左侧 0–108px（`dx≤90` 命中文件名，`dx≥105` 全被 ✎/🗑 接走） |

- [x] **根因（源码确认）**：`index.html` 里文件行的行操作区是**绝对定位浮层**——
      `.code-tree-actions { position: absolute; top: 2px; right: 0; z-index: 2 }`，
      而 `.code-tree-file button { width: 100% }`，两区**几何上完全重叠**。
      「行右预留 46px」只做在按钮的 `padding-right` 上（内容不越界），不构成命中测试的
      屏障 —— 指针落在谁身上只看谁在上面。
- [x] **走过的弯路（如实记录，防重犯）**：先试「给容器收窄宽度」
      （`width: fit-content`）——**治不了根**：实测容器宽度仍是 **131px**（比它自己
      两个按钮还宽），因为绝对定位盒 + `inline-flex` 被块化后，宽度由包含块决定。
      第一版审计脚本还据此写了两条**误报**（判据错在「查盘上文件」与「点完立刻读
      DOM」，与 CSS 无关），已按三步自检改掉。根因是「两区重叠」，所以修法必须让它们
      **不重叠**。
- [x] **修法（改布局，不改事件）**：文件行改成 flex 兄弟——
      `.code-tree-file { display: flex; align-items: center }`、
      `.code-tree-file button { flex: 1 1 auto; min-width: 0 }`（占剩余宽度）、
      `.code-tree-file .code-tree-actions { flex: none }`（只占自身 ~55px）。
      目录行保持绝对定位（`details > summary` 不便插兄弟），`.code-tree-dir` 那半边
      行为零变化。事件委托（`#code-tree` 上的 `[data-code-file]` 与
      `[data-tree-op]` 两路）**一字未改**。
      修后实测：按钮 170px、操作区 55px，**按钮正中央命中 `SPAN.code-tree-name`**，
      行内每一处（含 dx=165）都命中文件名按钮。
- [x] 测试守卫：
      * `tests/js/code-tree-actions-width.test.mjs`（新，4 条纯结构守卫）：
        文件行操作区不得再 `position:absolute`、必须 `flex:none`；文件行必须
        `display:flex` 且按钮 `flex:1 1 auto`、不得再用 `padding-right` 预留；
        目录行仍是绝对定位 + summary 仍留 padding（回退护栏）；hover 显形规则仍在
        （默认 `display:none`）。
      * `tests/browser/code-tree-click.spec.mjs`（新，2 条真机）：真鼠标点文件名 →
        编辑器真的打开（活动标签 = main.c）、`hover()` 不再被拦；几何判据——操作区
        宽度 ≤70px、横向覆盖 ≤40%、**文件名按钮正中央必须命中按钮自己**。
- [x] **反向验证（本单关键）**：把文件行改回修前形态（`display:block` +
      按钮 `padding-right:46px` + 操作区对文件行也 `position:absolute`）→
      **两侧同时变红**：纯结构守卫红 1 条；真机 spec **2/2 全红**，报错逐字为
      `… subtree intercepts pointer events` + `文件名按钮正中央命中的是 BUTTON.code-tree-act`。
      恢复后：结构守卫 4/4 绿、真机 spec 2/2 绿，grep 确认无 `TEMP 反向验证` 残留。
- [x] 归零回归（修后实测）：全量 pytest 绿、`node --test "tests/js/*.test.mjs"`
      **1499 pass / 0 fail**、`node --test tests/browser/code-tree-click.spec.mjs` 2/2。

**没做（如实记录）：**
- 没有为了「让 hover 通过」而给操作区加 `pointer-events:none` 之类——那会让 `✎/🗑`
  也点不动（结构守卫里专门写了一条禁止这么绕过）。
- 没有重做操作按钮的交互形态（悬浮显形、点击弹输入框）——原设计与实现都对，错的只是
  它与文件名按钮的**几何关系**。
- 目录行（`.code-tree-dir`）未改：它的 summary 与操作区同样重叠，但 `details/summary`
  的可点区语义与文件按钮不同（summary 是展开/收起，操作区在行右 46px 内），
  本轮**没有真机复现**其点击问题，故不动（宁缺勿滥，避免无证据的改动）。
