# 02 — 共享壳：static/js/app.js（$ / api / 主题 / toast / state / tabId 会话）

**要做什么：** 跨 tab 共享件从 index.html 主体迁入 `static/js/app.js`：`$`（getElementById）、handle / apiGet / apiPost / apiPut / apiDelete、主题三函数（currentTheme / applyTheme / initTheme + initTheme() 调用）、KIND_TEXT、toast / TOAST_ICON、`state` 对象所有权（含 setState）、tabId 会话（TAB_ID_KEY + register/pagehide beacon）、initBtnIcons IIFE（整页 `[data-ico]` 图标注入）。index.html 主体改从 app.js import。**本票建好 ui 模块的依赖地基（禁环规则：app.js 不 import 任何 ui 模块）。**

**被谁阻塞：** 无（fx 模块已在位；app.js 只依赖 fx 纯件——btnIcon）

**状态：** resolved（2026-08-27；JS 435 全绿、pytest 2465 全绿（115.76s）、diag 零 EXC（favicon 404 既有噪音）、smoke 11/11、探针 02 通过）

## 实施记录

- **重大数字修正（相对工单正文与 spec）**：refreshState（原 2346-2357）实际调 **renderToolchainStatus / renderPlatforms / renderModulePool 三个簇函数 + 赋值 `toolchains`**（正文只记了 renderPlatforms 一处）。裁定：**refreshState 留 host**（app.js import ui 簇 = 违反禁环成环），app.js 导出 `setState`（`export let state = null` + `export function setState(v) { state = v; }`）；host 内 refreshState 与启动 init 两处 `state = await apiGet("/api/state");` 改 `setState(await apiGet("/api/state"));`（脚本断言恰 2 处、改写后正则校验通过）；「拆出 renderPlatforms() 调用」的原方案废弃。
- app.js（新建，102 行）：迁入 12 名——$ / handle / apiGet / apiPost / apiPut / apiDelete / KIND_TEXT / currentTheme / applyTheme / initTheme（含 initTheme() 模块级调用）/ toast + TOAST_ICON / initBtnIcons IIFE / TAB_ID_KEY + tabId 会话（top-level：sessionStorage + crypto.randomUUID + fetch register + pagehide sendBeacon）/ state + setState；全部逐字搬移（toast 手动 & < " 转义、theme localStorage 防闪、tabId 协议均原样）；仅 import fx/btn-icon.js；头部注释声明禁环规则（不 import ui、state 属性写合法/整换走 setState、不挂 window 桥）。
- index.html：apply-02.mjs（CRLF 感知 + 内容锚定）：host import 行插入（workflow.js 之后：`import { $, handle, apiGet, apiPost, apiPut, apiDelete, KIND_TEXT, state, setState, toast } from "/js/app.js";`）；8 块替换为「已迁至 static/js/app.js（阶段 2 工单 02）」注记（主题块 / API 辅助块 / KIND_TEXT 行 / 标签会话块 / state 声明行 / initBtnIcons IIFE / Toast 块；页签分发器与生成页状态声明 lets（llmPricesDefaults/selectedSlugs/expanded/pythonTemplates/warnings/scorePoints/instances/instancePinTarget 2337-2344→2276-2283）留 host）；2 处 state 赋值改 setState；末校验 12 名在 index.html 无 `function|const` 定义。8902 行（8989 → 8902，净 -87）。
- **脚本首跑两处抛错修正**：① `let state = null;` 带尾注释 `// GET /api/state`，trim 精确匹配失败 → 改 includes；② step 8 废探针行（`trim()==="}" && indexOf("setTimeout")!==-1` 恒假）先于真逻辑执行 → 删除。抛错均在写盘前，文件未写坏。
- **编辑后人工发现的漏网（重要教训）**：脚本待删块清单**漏了 `const $ = ...` 单行**（位于「use strict」后）——host import 的 `$` 与原 `const $` 模块级重名 = `SyntaxError: Identifier '$' has already been declared`，会杀死整个主体 module。脚本跑完后 grep 残差发现 → 编辑工具删除该行；残差校验补上 `$`。教训：删块清单必须覆盖一切「名字与 import 重名」的顶层声明（含 1 行 const）。
- 测试重指向：tests/js/btn-icons.test.mjs「注入逻辑存在」钉（原钉 index.html 的 `function initBtnIcons()` / `querySelectorAll("[data-ico]")` / `insertAdjacentHTML("afterbegin", btnIcon(b.dataset.ico))`）改读 app.js（新增 appJs 读入）；data-ico 覆盖/高频按钮/按钮文案三段 html 断言不动。
- 验证：node --test 435 全绿；pytest 2465 全绿；diag 零 EXC = 主体 module 无 SyntaxError；smoke 11/11；探针 probe-02-app.mjs（CDP 9251）：window.$/toast/handle 均 undefined（无窗污染）✓ 主题按钮接线 + dark→light 切换 ✓ data-ico 首元素含 svg（initBtnIcons 已注入）✓ 页签分发器（library 切换 active）✓ gen-banner hidden（state 初始化成功）✓ /js 资源 20 个（19 fx + app.js）✓。

- [x] 新建 `static/js/app.js`：共享件逐字搬移 + export + 头部注释（共享壳、禁环规则、state 所有权）
- [x] index.html：CRLF 感知脚本删 8 块 + host import 行追加（10 名）
- [x] refreshState 留 host；其与启动 init 的 `state =` 改 `setState(`
- [x] tests/js/btn-icons.test.mjs 结构钉重指向 app.js
- [x] `node --test` 435 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + 探针 02 通过 + grep 零残留
- [x] 中文提交 + CHANGELOG 记录

## 风险点（待跟踪）

- refreshState 中 `toolchains = ...` 仍靠 body 的 `let toolchains`——工单 16 迁 E 簇时需 setter（已记录在工单 16 风险点）。
- host import 面 10 名在后续 ui 簇迁出后仍被主体胶水引用；收尾工单 20 核对 import 清单最小化。
