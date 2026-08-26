# 23 — host 残留渲染迁移：new-platform 下拉归 ui/master.js

**要做什么：** 消除 host 残留的一处跨 tab DOM 渲染（评审发现 3，backlog 4.3）——index.html 启动 IIFE 内 L2593-2594 `$("new-platform").innerHTML = state.platforms.map(...)` 是母版 tab「新增平台」下拉的 options 渲染，属 master 簇胶水（工单 04 范围）。迁移为 ui/master.js 导出 `renderNewPlatformOptions(platforms)`（参数化，esc 已自 fx/core.js import），host 启动 IIFE 改一行调用，host import 行追加该名。

**被谁阻塞：** 无

**状态：** resolved（代码已于 f26e1fa 提交，2026-08-27 收尾时补翻状态）

## 验收标准

- [ ] `ui/master.js` 新增并导出 `renderNewPlatformOptions(platforms)`（与现 L2593-2594 等价：`<option value="${esc(p.id)}">${esc(p.name)}</option>`）
- [ ] index.html：L2593-2594 内联渲染删除，改 `renderNewPlatformOptions(state.platforms);`，master 的 host import 行追加该名
- [ ] 新增 `tests/js/master-render.test.mjs` 守卫：断言 ui/master.js 含 `renderNewPlatformOptions` 且 index.html 不含 `$("new-platform").innerHTML`（先红后绿）
- [ ] node --test 全绿 + diag 零 EXC + smoke 11/11 + 母版 tab 新增平台下拉实况（options 数与 state.platforms 一致）
- [ ] 中文提交

## 实施记录

- ui/master.js 新增 `export function renderNewPlatformOptions(platforms)`（loadMasters 之后，含注记）；index.html L2239 import 行追加该名；启动 IIFE L2593-2594 两行内联渲染改一行调用 `renderNewPlatformOptions(state.platforms);`。
- 新守卫 tests/js/master-render.test.mjs（2 条：master.js 定义 + 导出；index.html 无 `$("new-platform").innerHTML`）——实现前红、实现后绿；全量 node --test 447/447。
- smoke 11/11（8 tab 存在 + 切换 + main.c 高亮）；diag 复跑零 EXC（pwsh-26 于工单 21 后、pwsh-29 于本票后，见 25 记录）。
