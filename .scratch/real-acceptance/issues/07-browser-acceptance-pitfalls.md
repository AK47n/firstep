# 07 — 浏览器真机验收的四个姿势坑（写进约定，别再各踩一遍）

**要做什么：** 把第十六轮 B24/A2/A3 浏览器验收时踩到的四个坑固化成**可复用姿势**——
三个是本轮新发现（其一已在第十五轮记录过同族现象），都表现为「脚本红/挂住，产品其实没问题」，
每次重踩平均烧 20~40 分钟。

**被谁阻塞：** 无。

**状态：** ready-for-agent（低风险收尾单；可与任一真机单合并做）

## 四坑（本轮逐条实测）

### 坑 1 · 折叠 + 页签：元素 `display:none`，`fill/click` 等 30s 超时

第 11 步「修订与深化」卡默认折叠，卡内又是**页签式**（`#revise-tabs .revise-tab[data-tab="revise"]`）。
不展开 + 不切页签，内部元素全 `display:none`，playwright 的 `fill/click` 会一路等到 30s 超时，
报错信息只说「element is not visible」，看不出是页签没切。

**姿势**：`waitForSelector(sel, {state:"attached"})` → `classList.remove("collapsed")` +
点 `.revise-tab[data-tab=...]` → 再 `waitForSelector(sel, {state:"visible"})`。
（顺带记下 id 事实：修复中心卡 = `#card-fix-center`；`#compile-banner` 挂在 `#generate-result` 内，
**只有走过一次生成的会话**里结果区才可见——第十五轮坑位 4 的同类。）

### 坑 2 · `waitForFunction(fn, arg, options)` 的超时位置

超时必须放**第三个参数**。写成第二个会被当成 `arg`，于是拿到**默认 30s** 超时——
现场表现为「我明明写了 15 分钟，却 30 秒就红」，本轮因此误判两次「页面挂死」。

### 坑 3 · `page.evaluate` 里 await 长流程 = 单次 CDP 调用挂几十秒

`await page.evaluate(async () => { await mod.reviseAnalyze(); })` 会把整条 CDP 调用
压在页面里等（分析实测 **28s**，视觉/深化分钟级），期间 node 侧任何 `page.evaluate`
都可能拿不到响应，看起来像「渲染进程无响应」。诊断探针实测：**kick off 不 await +
node 侧轮询 DOM** 时，页面一切正常（
`.scratch/revise-deepen/verify-16-revise-hang-diag.{txt}`：t+28s 分析完成、无 pageerror）。

### 坑 4 · 模态确认不点 = 请求根本不发

`reviseApply` / `reviseRollback` 各有一层 `confirmModal`（覆盖式重生成明示 / 回滚危险确认）。
不点确认，`POST /api/revise/apply` **不会发出**——现场表现为「执行阶段状态行一直空、
服务端日志里只有 analyze」。用 `filter({hasText: /执行修订|确认回滚/})` 按按钮文字点最稳。

## 修复方向（实施会话定）

1. `.scratch/cdp-harness.mjs`（或新 `.scratch/browser-harness.mjs`）加两个助手：
   - `expandCard(page, cardId, tabSelector)`：展开卡 + 切页签 + 等可见（坑 1）；
   - `pollUntil(page, fn, {timeoutMs, every})`：node 侧轮询（坑 3）。
2. 在 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md` 的「B 组统一前置」
   段落里补一条**姿势清单**（把坑 1-4 写进去），供后续真机单直接照抄。
3. 可选：把「`waitForFunction` 超时位置」写进 `.scratch/cdp-smoke-run.mjs` 顶部注释。

## 验收标准

- [ ] 助手函数入库且被至少一个新脚本实际使用（B24 的 `verify-16-revise-render.mjs` 可改为调用它，作为回归样本）
- [ ] 挂账单 B 组前置段落含四坑清单（逐条一句 + 正确姿势）
- [ ] `node --test tests/js/*.test.mjs` 绿（若新增纯件测试）

## 实施提示词（新会话粘贴）

> 工单：`.scratch/real-acceptance/issues/07-browser-acceptance-pitfalls.md`（先读全文）。
> 背景：第十六轮 B24 浏览器段三次红/挂（`.scratch/revise-deepen/verify-16-revise-{live,render}-run.txt`、
> `verify-16-revise-analyze-trace.txt`、`verify-16-revise-hang-diag.txt`）。
> 任务：把四个姿势坑固化成 `.scratch/` 共用件助手 + 挂账单 B 组前置清单，并让 B24 脚本改用它作为回归样本。
> 文件边界：`.scratch/cdp-harness.mjs` 或新增 `.scratch/browser-harness.mjs` + `.scratch/revise-deepen/verify-16-revise-render.mjs` + 挂账单 01 的 B 组前置段；产品代码零改动。
> 验收：改后的 B24 脚本仍 19/19 全绿（真机跑一次），助手被至少一个脚本引用。
