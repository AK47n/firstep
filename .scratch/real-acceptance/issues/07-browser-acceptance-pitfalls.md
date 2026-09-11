# 07 — 浏览器真机验收的四个姿势坑（写进约定，别再各踩一遍）

**要做什么：** 把第十六轮 B24/A2/A3 浏览器验收时踩到的四个坑固化成**可复用姿势**——
三个是本轮新发现（其一已在第十五轮记录过同族现象），都表现为「脚本红/挂住，产品其实没问题」，
每次重踩平均烧 20~40 分钟。

**被谁阻塞：** 无。

**状态：** resolved（2026-09-11 落地：`.scratch/browser-harness.mjs` 两助手 +
挂账单 01 B 组姿势清单 + B24 脚本改用它复跑）

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

- [x] 助手函数入库且被至少一个新脚本实际使用（B24 的 `verify-16-revise-render.mjs` 可改为调用它，作为回归样本）
      —— 新文件 `.scratch/browser-harness.mjs` 导出 `expandCard(page, cardId, tabSelector, {attachMs, visibleMs})`
      与 `pollUntil(page, fn, {timeoutMs, every, label})`（零依赖、不 import playwright，page 由调用方传）；
      `verify-16-revise-render.mjs` 三处 `pollUntil` + 展开/切页签段全部改用它（19 项真机复跑全绿，见下）
- [x] 挂账单 B 组前置段落含四坑清单（逐条一句 + 正确姿势）
      —— `01-real-machine-acceptance.md`「B. 浏览器 / CDP 目检与截图」的**姿势清单**段（助手入口 + 四坑 + id 事实）
- [x] `node --test tests/js/*.test.mjs` 绿（若新增纯件测试）
      —— 新增 `tests/js/browser-harness.test.mjs`（9 条：选择器归一 / done 判据 / 轮询终态与超时 /
      `evaluate` 抛错不炸 / 展开+页签顺序与可见性见证 / 见证超时抛错带上下文）

## 实施记录（2026-09-11）

| 改动 | 位置 |
|---|---|
| 新助手文件（零依赖、page 由调用方传——可假 page 单测）：`expandCard` = `attached` → 页面内 `classList.remove("collapsed")` + DOM 点页签 → 等**页签条/卡** `visible`（折叠态 `.card.collapsed > *:not(h2)` 整块 `display:none`，故这是「卡真展开了」的可靠见证；超时抛错带上下文：步骤没显示 / 选择器不对）；`pollUntil` = node 侧轮询，返回**最后一次观测** + `{done, elapsedMs, observations, timeout?}`，`evaluate` 抛错按未就绪处理，超时打 stderr 一行 | `.scratch/browser-harness.mjs`（新） |
| 头部把四坑写成姿势说明（含「间隔用本地 sleep、不绑 playwright 生命周期」与 id 事实） | 同上 |
| 纯件测试（假 page，不起浏览器） | `tests/js/browser-harness.test.mjs`（新，9 条） |
| B24 脚本改为助手回归样本：删掉脚本内自写的 `pollUntil`（局部 `poll` 只做超时 note）、展开+切页签段改 `expandCard`；头部四坑改为指向助手与本文 | `.scratch/revise-deepen/verify-16-revise-render.mjs` |
| 挂账单 01「B 组统一前置」补姿势清单（四坑逐条 + 正确姿势 + 助手入口 + id 事实） | `.scratch/real-acceptance/issues/01-real-machine-acceptance.md` |
| 可选第 3 条落地：批跑器顶部注释补「`waitForFunction` 超时在第三个参数」+「长流程别在 evaluate 里 await」两条 | `.scratch/cdp-smoke-run.mjs`（注释） |

**真机复跑（B24，2026-09-11）**：`node .scratch/revise-deepen/verify-16-revise-render.mjs`
——**19 项全绿**（分析段 11 + 执行段 5 + 回滚段 3），证据
`.scratch/revise-deepen/verify-16-revise-render.{txt,json}` + `verify-16-revise-progress.txt`
（脚本用新助手跑通同一场景：`expandCard` 展开 `#card-revise` + 切修订页签 → 历史目录补题面 →
分析渲染 3 条目块 / 28 chip → 确认执行（真 SSE 三态「备份 → 重生成 → 编译验证」）→
回滚后 `main.c` sha 逐字节复原 `47c9c6d3d850`，`已回滚 149 项`，页面零 JS 异常）。

**回归**：全量 `pytest` **3971 passed, 1 warning**；`node --test tests/js/*.test.mjs`
**1444 pass / 0 fail**（本单新增 `tests/js/browser-harness.test.mjs` 9 条）。

**没做/边界**：

1. **模态确认（坑 4）没做成助手**：本轮只按工单加两个助手，脚本里两处 `confirmModal` 仍是
   自带代码（已是正确姿势：等模态 + `filter({hasText:/执行修订|确认回滚/})` 按文字点）。
   要收成第三个助手 `confirmModal(page, {text})` 时注意：**别用「等状态行」代替等模态**
   （不点确认请求根本不发，状态行永远空）。
2. **坑 2（`waitForFunction` 超时位置）无法用助手消灭**：`pollUntil` 绕开了它，但脚本里
   直接写 `waitForFunction` 的地方仍会踩——故只做成「两处注释 + 清单一条」。
3. 助手的 `every` 间隔用本地 `sleep`（不是 `page.waitForTimeout`）：页面被关掉后仍能走到
   超时并如实返回，代价是与 playwright 的 fake timer 无关（本仓库没有用 fake timer 的脚本）。
4. **本轮真机那次 `wasCollapsed=false`**（页签命中 `true`）：卡折叠状态是持久化的，上一次
   跑完就留在展开态，所以真机这次实际走的是「已展开 + 切页签 + 等可见」这条分支；
   **「折叠 → 展开」那条分支由纯件测试覆盖**（`tests/js/browser-harness.test.mjs` 的
   「顺序 = attached → 页面内展开+点页签 → visible 见证」用 `collapsed: true` 的假 DOM）。
   要真机复现折叠态：换一个干净 profile 或用 `expandCard` 前先 `classList.add("collapsed")`。

## 实施提示词（新会话粘贴）

> 工单：`.scratch/real-acceptance/issues/07-browser-acceptance-pitfalls.md`（先读全文）。
> 背景：第十六轮 B24 浏览器段三次红/挂（`.scratch/revise-deepen/verify-16-revise-{live,render}-run.txt`、
> `verify-16-revise-analyze-trace.txt`、`verify-16-revise-hang-diag.txt`）。
> 任务：把四个姿势坑固化成 `.scratch/` 共用件助手 + 挂账单 B 组前置清单，并让 B24 脚本改用它作为回归样本。
> 文件边界：`.scratch/cdp-harness.mjs` 或新增 `.scratch/browser-harness.mjs` + `.scratch/revise-deepen/verify-16-revise-render.mjs` + 挂账单 01 的 B 组前置段；产品代码零改动。
> 验收：改后的 B24 脚本仍 19/19 全绿（真机跑一次），助手被至少一个脚本引用。
