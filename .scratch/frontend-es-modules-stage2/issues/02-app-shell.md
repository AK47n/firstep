# 02 — 共享壳：static/js/app.js（$ / api / 主题 / toast / state / tabId 会话）

**要做什么：** 跨 tab 共享件从 index.html 主体迁入 `static/js/app.js`：`$`（getElementById）、handle / apiGet / apiPost / apiPut / apiDelete、主题三函数（currentTheme / applyTheme / initTheme + initTheme() 调用）、KIND_TEXT、toast / TOAST_ICON、`state` 对象所有权（含 refreshState）、tabId 会话（TAB_ID_KEY + register/paste beacon）、initBtnIcons IIFE（整页 `[data-ico]` 图标注入）。index.html 主体改从 app.js import。**本票建好 ui 模块的依赖地基（禁环规则：app.js 不 import 任何 ui 模块）。**

**被谁阻塞：** 无（fx 模块已在位；app.js 只依赖 fx/core 等纯件——若使用）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 共享区 = 2214-2360：imports 2217-2234；`"use strict"` 2235；`$` 2236；主题 2242-2264（initTheme() 调用 2264）；handle 2269；apiGet 2278 / apiPost 2279 / apiPut 2284 / apiDelete 2289；KIND_TEXT 2296；TAB_ID_KEY 2301；tabId 会话 2302-2309；state 2335；refreshState 2345（**函数体内 @2354 调 renderPlatforms()——拆出该调用**：app.js 不 import ui，host 启动改为 `refreshState(); renderPlatforms();` 并列）；toast 8799 / TOAST_ICON 8798；initBtnIcons IIFE 6963（全页 `[data-ico]`；btn-icons.test.mjs:38-40 钉 `function initBtnIcons()` + `querySelectorAll("[data-ico]")`）。
- `state` 写点：直接赋值仅 refreshState 2345 + init 9009；属性写（`state.modules=...` @5800/5850/5960 等）留各 ui 簇，经 `import { state }` 属性写合法。
- 页签分发器（2314-2330）**留 host**：它调各 tab load\*（library→loadLibrary；reference→loadReferences+loadKitVocabulary；pdf→loadPdfs；topic→loadTopics+loadTopicGroupVocabulary；master→loadMasters；changelog→loadChangelog；settings→loadSettings+loadRecentWorkflows+renderUsageStats）——含 `stepDoneSet.size==0` 判定 @2321（steps 簇导出 stepDoneSet 后 host import）。
- 主题防闪 head script（7-14 行）不搬（唯一遗留独立内联 script）。

## 检查表

- [ ] 新建 `static/js/app.js`：上述共享件逐字搬移 + `export`（$ / handle / apiGet / apiPost / apiPut / apiDelete / KIND_TEXT / state / refreshState / toast / initBtnIcons / tabId 会话件 / 主题件）+ 头部注释（共享壳、禁环规则、源自阶段 2 工单 02）
- [ ] index.html：用 CRLF 感知行区间脚本删除已搬定义（**$order 按文件物理升序**；该批散落 2214-2360 / 6963 / 8798-8823 三处，末键单独收尾）+ 主体 module 顶部 import 行追加 `import { ... } from "/js/app.js"`
- [ ] refreshState 的 renderPlatforms() 调用拆到 host（init 内并列调用），行为不变
- [ ] tests/js/btn-icons.test.mjs：结构钉重指向 app.js（initBtnIcons + `[data-ico]` 选择器）
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + grep 零残留
- [ ] 中文提交

## 风险点

- refreshState 若被他处调用（grep 遍历），调用点改走 host/模块链；app.js 内不得出现对 ui 函数的引用（禁环）。
- tabId 会话的 register/pagehide 若依赖 `document.visibilityState` 等运行时环境，逐字搬移即可（top-level 执行同 defer）。
