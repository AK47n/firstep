# 01 — 第11步页签骨架与切换

**要做什么：** 用户打开第 11 步「修订与深化」卡时，先看到 h2 下方的页签条（修订 / 任务推进 /
参数速调 / 交付），点击或左右方向键切换面板，一次只看一个分区；默认激活「修订」，上下文
加载成功后若用户还没手动切过页签，自动切到「任务推进」一次；页签条有统一样式、窄屏可横向
滚动；卡片右上角折叠功能不受影响。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] index.html：`#card-revise` 的 h2 下插入 `<nav id="revise-tabs" class="revise-tabs" role="tablist">`，
      4 个 tab 按钮 `data-tab="revise|tasks|params|delivery"`（role=tab / aria-selected 同步）
- [x] index.html：第 11 步原 5 大块内容拆进 4 个 `section.revise-panel`
      （`id="revise-panel-{revise|tasks|params|delivery}"`），非激活面板加 `hidden`；
      `#tasks-box` 中「⚙️ 参数速调」「🚀 交付」两个 card-group 完整搬到各自 panel，无内容遗漏
- [x] `fx/revise-tabs.js`（纯函数单源）：`reviseTabsHTML(tabs, active)`、
      `reviseTabNext(active, dir, count)`、`revisePanelFor(tab)`；`tests/js/revise-tabs.test.mjs`
      覆盖并全绿
- [x] `ui/revise-tabs.js`：init（默认 revise）、点击/方向键切换（panel hidden 切换 +
      aria-selected）、`revise-context-loaded` 且未手动切换时自动激活 tasks 一次；
      index.html 模块 import 清单加 `fx/revise-tabs.js` / `ui/revise-tabs.js` 两行
- [x] 现有 `reviseRenderContext` 对 `#revise-context/#revise-analyze-box/#revise-exec-box/#tasks-box`
      的 hidden 生命周期与 panel 显隐不冲突（加载上下文后各块正常显示）
- [x] 浏览器验证：4 页签切换、方向键、卡片折叠仍生效、窄屏页签条可滚动
