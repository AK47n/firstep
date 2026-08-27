# 工单 02：前端选型参考展开（suggestionChip 升级）

> 来源：.scratch/buy-guide/spec.md §2.3
> 状态：resolved（双轴评审 + 浏览器 E2E 18/18：展开/收起/徽标/旧样回退/不误触 data-remove；CSS 特异性修复 .chip.out.sugg-chip）

**要做什么：**
- `static/js/ui/generate-recommend.js` 的 `suggestionChip(s)` 升级：
  - `s.solutions` 非空 → chip 可展开（点击 toggle）：名称 + 「⤵ N 方案」徽标，展开后下方渲染「选型参考」面板。
  - 面板每方案一行：`名称` + `[接口]` + `[价格]` + 徽标（`recommended` →「推荐」；`selected === solution.name` →「AI 建议」，两徽标可共存）+ 备注 + `适用：suitable`。
  - `s.solutions` 空 → 现行为（仅 name + 「需自备」）。
  - 展开状态用 CSS class toggle（active 态），再次点击收起；渲染函数保持纯函数（data → html），事件委托走现有 box 的 click（注意现有 data-remove 委托共存）。
- `static/js/fx/recommend.js`（如存在渲染纯函数）或就近纯函数模块：方案行渲染纯函数 + 单测（fx-guard DOMAINS 若涉及需登记）。
- 样式：使用现有 chip / item 类，新增 `.selection-options` 等少量 CSS（index.html 内联样式区或既有 style 块），保持 0 构建原生 ESM。

**被谁阻塞：** 01（solutions 载荷）。

**验收标准：**
- [x] 展开/收起 toggle 正常（点击 chip 区，不误触 data-remove）
- [x] 方案行渲染：名称/接口/价格/备注/适用 + 徽标（推荐 / AI 建议 / 共存 / 都无）
- [x] solutions 空回退旧样
- [x] js 单测覆盖渲染纯函数 + 徽标逻辑（tests/js/recommend.test.mjs 12 条）
- [x] 全量 pytest + JS 绿（507 passed）；中文 commit
