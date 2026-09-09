# 01 — 偶发页面挂死：`Page.reload` 后渲染进程不响应（CDP 命令永不返回）

**要做什么：** 定位并修掉「CDP 冒烟跑完后，下一次 `Page.reload` 偶发导致渲染进程无响应」的根因。
现象：`Runtime.evaluate` 永不返回（20s 超时守卫报 `CDP 无响应（20s）: Runtime.evaluate`），
`/json/list` 里页面 target 仍在，**关掉该标签页新开一个即恢复正常**（webapp 200、`/json/version` 正常，
日志显示 `POST /api/tabs/bye 200`——服务端无异常）。

**被谁阻塞：** 无——可立即开始。

**Type:** task
**Status:** resolved

## 现象与复现（2026-09-09 第七轮，headless Chrome 152 + CDP 9251）

| 观察 | 证据 |
|---|---|
| 偶发，非确定性 | 同一支 `overhaul/smoke-05.mjs`：fresh tab 单跑 **11/11 PASS**；紧接着 `smoke-04` 后跑则挂死 |
| 挂死时服务端正常 | `webapp: 200`、`/json/version` 正常、日志尾行 `POST /api/tabs/bye 200` |
| 页面 target 仍在 | `/json/list` 有 `page http://127.0.0.1:8000/`，但对它的 `Runtime.evaluate` 不返回 |
| 重建标签页即恢复 | `json/close/<id>` + `json/new?<url>` 后同一脚本立刻全绿 |
| 已排除 | 不是 CDP 端口/浏览器进程死（`/json/version` 有响应）；不是 webapp 死；不是脚本自身死循环（输出为空即卡在第一个 CDP 命令） |

**已做的缓解（非修复）**：10 支 `overhaul/*.smoke*.mjs` 的 `cdp()` 加 20s 超时守卫——脚本从「静默挂死」
变「显式报错」（`CDP 无响应（20s）: <method> —— 页面可能已挂死`）。**根因未查**。

## 诊断方向（建议按序）

1. **CDP 侧先取证**（低成本、最能定性）：挂死时接 CDP 浏览器端点，抓
   `Inspector.targetCrashed` / `Page.frameDetached` / `Page.loadEventFired` 是否触发；
   或挂死时对同一 target 试 `Page.enable`（若也不返回 = 渲染进程真的卡死/崩溃，而非单命令问题）。
2. **对齐「5000 行 + 窗口化重建」**：疑似与 `smoke-08`/`smoke-09`（5000 行 `big.c`、窗口化
   `winBuild` + 大 `.code-edit` 高度 ≈104k px）相关——挂死样本多出现在跑过这两支之后。
   可试：跑完 `smoke-08` 后只做 `Page.reload` 循环 N 次，统计挂死率。
3. **`beforeunload` / 标签会话路径**：`fx/exit-guard.js`（未保存退出保护）与 webapp 的标签会话机制
   （`POST /api/tabs/bye`）在 reload 时会跑；确认是否有同步阻塞（弹窗、同步 XHR、无限等待）。
4. **headless 专属？**：同一操作序列在非 headless Chrome 手动复现一次（若只在 headless 出现，
   则定性为测试环境问题，脚本侧改为「每支前重建标签页」并记录）。

## 验收 checklist

- [x] 复现步骤固化（脚本或手工步骤），挂死率可测（如 20 次 reload 0 挂死）。
- [x] 根因写明（渲染进程崩溃 / 布局死循环 / 会话机制阻塞 / headless 专属），带 CDP 事件证据。
- [x] 若为产品缺陷：修复 + 回归（`smoke-08`/`smoke-09` 跑完后 reload 循环不挂死）。
      ——**结论：不是产品缺陷**（见下「根因」）；产品侧顺带修出两处真缺陷（见「同批修复」）。
- [x] 若确为 headless 测试环境问题：在 `.scratch/code-page-vscode-overhaul/` 冒烟脚本头部写明
      「每支前重建标签页」的约定，并把该约定写进 `.scratch/real-acceptance` 的 B 组前置说明。

## 根因（2026-09-09 第八轮 · 实跑取证，非推断）

**结论：不是产品缺陷，是「自动化侧没有应答 beforeunload 对话框」——但触发条件是产品态的
「编辑器有未保存修改 + 页面有过用户手势」，故必须由脚本侧约定消解。**

挂死链条（每环都有实跑证据）：

1. **前置条件**：编辑器有脏标签（`tab.content !== tab.savedContent`）**且**页面拿到过用户手势
   （CDP `Input.dispatchKeyEvent` 等 trusted 输入）。
2. **触发**：此时 `Page.reload` → Chrome 弹**原生 beforeunload 对话框**
   （CDP 事件 `Page.javascriptDialogOpening`，`params.type === "beforeunload"`）。
3. **挂死**：对话框无人应答时，渲染进程停在「等对话框结果」态——
   `Runtime.evaluate` / `DOM.getDocument` / `Page.navigate` 等**渲染进程侧**命令永不返回，
   而**浏览器进程侧**命令（`Input.dispatchKeyEvent`、`Page.handleJavaScriptDialog`）仍正常应答
   （据此可与「渲染进程崩溃」区分：target 未消失、无 `Inspector.targetCrashed`）。
4. **恢复**：`Page.handleJavaScriptDialog{accept:true}` 一到就恢复；重建标签页同样恢复
   （clean 页无脏缓冲 → 无对话框）。

### 证据矩阵（`.scratch/code-editor-cdp-hang/` 下脚本可复跑）

| 实验 | 脚本 | 结果 |
|---|---|---|
| 单脚本 reload 循环（plain / 5000 行编辑器） | `repro-reload-hang.mjs --mode=plain/editor --cycles=20` | **0 挂死**（挂死率 0%）——排除「reload 本身」与「大文件窗口化」 |
| 背靠背序列（`smoke-04` → `smoke-05`） | `repro-sequence.mjs` | **必挂**（第 2 支 75s 超时）——复现第七轮现象 |
| 浏览器端点事件 | `forensics-browser.mjs` | 挂死时 target **仍在**、无 `targetCrashed`/`frameDetached`；20s 后仍无响应 |
| 首个不返回的命令 | `probe-first-hang.mjs` | `Page.reload` 返回 OK → **`Runtime.evaluate` / `DOM.getDocument` / `Page.navigate` 全超时**；`Input.*` / `Page.handleJavaScriptDialog` 正常 |
| 对话框假设 | `probe-dialog-unblock.mjs` | 挂死现场事件序列含 **`Page.javascriptDialogOpening`**；此时 `handleJavaScriptDialog` 返回「No dialog is showing」 |
| 三组对照 | `probe-dialog-type.mjs` | **A 脏 + 用户手势 = 弹框 + 挂死**；**B 脏但拦 beforeunload 无效**（捕获阶段也拦不住，注册在模块加载时）；**C 干净 = 不挂** |
| 谁留下的脏 | `probe-impact.mjs` | `smoke-04` 留 `dirty:["main.c"]` **且**最后一步派发 trusted 按键 → 有对话框；`smoke-01`/`smoke-08` 也留脏但无手势 → 不挂 |
| 修复验证 | `probe-fix-dialog.mjs` | **实验 D**：dialogOpening 一到就 accept → **reload 后 OK**；**实验 F**：注入式禁用 beforeunload **无效**（注入脚本早于模块注册） |
| 完全恢复 | `verify-recovery-clean.mjs` | **9/9**：应答后新文档就绪 / `/api/state` 200 / 编辑器可开文件 / 无残留脏 / 再 reload 不挂 |
| 约定有效性 | `self-test.mjs` | **10/10**：对照组必挂 → 约定组（每支前重建标签页）全绿 → harness 自动应答对话框 |

### headless 专属？

**不是 headless 专属**：真实浏览器里同一条件也会弹原生确认框（用户点「离开」即继续），
只是无人应答时同样会卡住渲染进程——差别在「有人点」还是「没人点」。
故定性为**自动化姿势问题**（headless 只是让「没人点」成为默认），处置 = 脚本侧约定 + harness 自动应答。

### 处置（已落地）

| 落地物 | 位置 | 作用 |
|---|---|---|
| 共用 CDP 工具 | `.scratch/cdp-harness.mjs` | `rebuildTab()`（每支前重建标签页）+ `connect()`（**对话框自动应答** + 每命令超时守卫 + `waitFor`/`ready`） |
| 批跑器 | `.scratch/cdp-smoke-run.mjs` | `--batch=<名>` 按约定逐支跑（每支前重建标签页）、挂死现场取证、自动恢复；`--no-rebuild` 用于对照复现 |
| 复现/取证/自测脚本 | `.scratch/code-editor-cdp-hang/*.mjs` | 上表全部可复跑 |
| 脚本头部约定 | `.scratch/code-editor-cdp-hang/README.md` | 约定文本 + 用法（供各批脚本头部引用） |
| real-acceptance B 组前置 | `.scratch/real-acceptance/issues/01-real-machine-acceptance.md` | 「每支脚本前重建标签页」+ 根因一句话 |

## 同批修复（顺带修出的两处真产品缺陷，均带 CDP 实跑 + 回归守卫）

1. **编译错误标记清不掉**（`code-editor-refine/smoke-05` 场景 5 FAIL）：
   `winRenderMarks` 的缓存复用分支把「缓存里带旧 error 段的清单」+「本次当前文件的错误段」拼起来，
   错误清空时 `extra` 为空 → 旧 `.code-mark-error` 被复用回来，**gutter 色点清了、标记层残留**，
   直到切标签（`renderPane` 清缓存）才消失。修 = `marksCache` 缓存键补 **编译错误签名**
   `compileSig`（与第七轮 `findQuery` 同一类修法）。守卫 = `tests/js/code-editor-window-guard.test.mjs`
   新增「marksCache 复用前提含编译错误签名」。
2. **打开文件竞态**（`code-editor-refine/smoke-02` 偶发 FAIL）：
   `openEditorFile` 是 async 且三处调用点都不 await → 快速连点两个文件时**晚到的旧请求
   抢走活动标签**（实测 `{"tabs":["b.c","a.c"],"active":"a.c","dirty":["a.c"]}`：用户点 b.c 却在 a.c 里编辑）。
   修 = 新增 `openSeq` 最新请求序号：只有「自己仍是最新请求」才 `activateTab`；晚到请求仍
   `renderTabs()`（**标签栏必须与模型同步**——只挡 activateTab 会留下「模型 2 个 tab / 标签栏 1 个」的错位，
   这是同一个 bug 的第二半）。`editJumpToFile` 据返回值跳过跳行。守卫 = 同文件两条断言。

## Comments

- 2026-09-09 第七轮：用户拍板「另开诊断单」。本轮只做缓解（20s 守卫），未查根因。
- 影响面：所有 CDP 冒烟脚本（约 40 支）——挂死会浪费一轮实跑时间且无输出，误判为「脚本没跑完」。
- 2026-09-09 第八轮：根因定位完成（beforeunload 对话框 + 无人应答）→ 定性为自动化姿势问题，
  落地 harness / 批跑器 / 约定 + 自测 10/10；顺带修出上述两处产品缺陷。原第七轮的「偶发」
  其实**不是随机的**：只要「上一支脚本留下脏缓冲 + 用过 trusted 按键」，下一支开头 reload 必挂。

