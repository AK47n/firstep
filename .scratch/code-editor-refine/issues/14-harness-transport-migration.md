# 14 — `refine/smoke-01` 换用 `cdp-harness` 传输层：消掉 exit 13（未落定 top-level await）

**要做什么：** 把 `.scratch/code-editor-refine/smoke-01.mjs` 自带的那套迷你 CDP 客户端
（自建 `WebSocket` + 无超时的 `cdp()`）换成第十一轮建议的共用传输层 `.scratch/cdp-harness.mjs`
（`connect()`：命令级 20s 超时守卫 + `beforeunload` 自动应答；`rebuildTab()`：每支脚本前重建
标签页）。**冒烟断言与场景一律不动**，只换传输层；然后连跑 14 轮以上确认不再出现
`exit 13`（Node 事件循环空掉时仍有未落定的 top-level await 的退出码），并且把
「exit code 异常」与「断言失败」在脚本输出里区分开报告。

**被谁阻塞：** 无——可立即开始（第十一轮「下一轮建议」第 2 项的落地）。

**状态：** resolved

## 为什么

第十一轮记录：`refine/smoke-01` 在长连跑里偶发红时，形态是「`await openFile` 挂住 →
**exit 13**」——自带客户端的 `cdp(method, params)` 是 `new Promise((resolve) => …)`，
**只有 resolve、没有 reject、也没有超时**：一旦某个渲染进程侧命令不返回（第十轮已定性的
`beforeunload` 原生对话框挂死，或现场劣化），整个脚本就停在未落定的 `await` 上，
Node 事件循环一空即 `exit 13` 且**不给任何 FAIL 行**。冒烟脚本「红得没有信息」正是这么来的。

`cdp-harness.mjs` 同时给到三件事，正好对准这三处：

| 缺口 | harness 给了什么 |
|---|---|
| 命令无超时（`await openFile` 挂住 → exit 13） | `cdp()` 每个命令默认 20s 超时，超时**显式 reject**（`hung: true`），不再静默卡住 |
| `beforeunload` 对话框无人应答 → 渲染进程挂死 | `connect()` 收到 `Page.javascriptDialogOpening` 立即 `handleJavaScriptDialog{accept:true}` |
| 上一支脚本留下的脏缓冲 | `rebuildTab()` 每支前重建标签页（批跑器已在用，脚本自身也兜一层） |

## 验收

- [x] `smoke-01.mjs` 已切换传输层：删除自建 `WebSocket` / `cdp()` / `waitFor()` / `fetchT()` 实现，
      改为 `import { connect, pageTarget, rebuildTab } from "../cdp-harness.mjs"`；
      `connect({ port: 9251, timeoutMs: 20000 })` 提供命令级 20s 超时 + 对话框自动应答
- [x] `rebuildTab()` 在脚本开头先重建标签页（clean 页 = 无脏缓冲 = 不弹框）
- [x] 全部冒烟断言与场景**未改**：`git diff` 逐行核对，`check(...)` 的**名字、表达式、顺序一字未动**，
      场景 1~6、观测器段与取证段逐字保留；改动只落在「传输层 + 首尾包装」——
      传输层替换（含 `new Promise((r) => setTimeout…)` → `sleep()` 的等价搬运）、
      场景体套一层 `async function main()`、末尾追加事件序列 dump（详见 Comments 的 diff 归类）
- [x] 脚本内区分报告：断言失败 → `exit 1`（打印 `N PASS / M FAIL`）；
      传输层/挂死类异常 → `exit 2`（打印 `TRANSPORT` 前缀 + CDP 事件序列）；
      另外挂 `unhandledRejection` / `uncaughtException` 兜底钩子（这类未落定 top-level await
      之前就是 `exit 13` 的来源，现在带原因显式退出）
- [x] 连跑 **20 轮**（≥14）实跑：**20 轮 20 次 exit=0 / 21 PASS / 0 FAIL**，
      无 exit 13、无断言失败、无 TRANSPORT（实跑记录 `.scratch/code-editor-refine/round12-harness-20.txt`）
- [x] 退出路径自检（反向验证，`.scratch/code-editor-refine/verify-harness-exit-paths.mjs` **11 项全绿**）：
      ① 命令级超时显式 reject（不是静默挂住）；② 真造 `beforeunload` 对话框（脏缓冲 + trusted 按键
      + 页面内 `location.reload()`）→ 出现 `dialogOpening type=beforeunload` 且被自动应答、
      220ms 内完成导航；③ **未捕获的超时命令 → exit 2**（而不是 exit 13）
- [x] **顺带修掉共用件的静默失效**：`cdp-harness.connect()` 从不 `Page.enable` ⇒
      `Page.javascriptDialogOpening`（Page 域事件）收不到 ⇒「对话框自动应答」形同虚设，
      渲染进程停在等应答态、下一次 `Runtime.evaluate` 撞 20s 超时。已改为 `connect()` 内
      无条件 `Page.enable` + `Runtime.enable`（带超时的 send，失败不阻断连接）；
      自检用例 ② **刻意不自己 enable**，即这条修复的回归断言

## Comments

- 2026-09-10 第十二轮（按第十一轮「下一轮建议」第 2 项）：传输层切换 + 20 轮连跑。
  原始 mini 客户端的三处缺口（无超时 / 不管对话框 / 不自建 clean 页）全部由 harness 覆盖；
  脚本头注释同步改写为「传输层 = cdp-harness」。

  **diff 归类（`git diff` 逐行核对，+67 / −32）**：
  ① 头部注释改写成传输层说明（+11）；② `import { connect, pageTarget, rebuildTab }`（+1）；
  ③ 删掉 `fetchT` / 自建 `WebSocket`+`cdp()`+`Eval()`、换成退出码常量 + `sleep` + 事件 dump（−32/+16）；
  ④ 前置段改 `pageTarget` 轮询 + `rebuildTab` + `connect`（+12）；⑤ 一行 `cdp("Page.reload")` →
  `send("Page.reload")`；⑥ 场景体套 `async function main()` 与末尾 `cdp.close()` / 事件 dump / try-catch（首尾包装）；
  ⑦ 4 处 `new Promise((r) => setTimeout(r, N))` → 等价 `sleep(N)`。
  **`check(...)` 的名字 / 表达式 / 顺序与场景 1~6 全部一字未动**；断言数切前切后同为 **21**
  （`git show HEAD:… | grep -c 'check('` = 21，切后 = 21）。

  **实测（webapp 8000 + Chrome headless CDP 9251）**：
  - 连跑 20 轮：`exit=0 × 20`、`21 PASS / 0 FAIL × 20`、TRANSPORT 0 轮、exit 13 **0 轮**
    （记录 `.scratch/code-editor-refine/round12-harness-20.txt`）。
  - 退出路径自检 `node .scratch/code-editor-refine/verify-harness-exit-paths.mjs` → **11 项全绿 / exit 0**：
    超时显式 reject（`hung: true` + 点名命令 + 「页面可能已挂死」；子进程 `child-timeout-caught.mjs`）、
    脏页 `location.reload()` 触发 `dialogOpening type=beforeunload` 并被 accept（导航 220ms 完成、
    应答后 `readyState=complete`）、未捕获超时 → **exit 2 + TRANSPORT 行**（子进程 `child-timeout-no-catch.mjs`）。
  - 兼容性复跑：`refine` 批 **10/10**、库 UI 批（`cdp-harness` 既有调用方）**4/4**。

  **本轮顺带查清的两条坑（供后续写 CDP 脚本的人省时间）**：

  1. **`connect()` 不 `Page.enable` ⇒ 自动应答静默失效**（本单已修，见验收最后一条）。
     实测形态：连接不 enable 时，脏页导航弹出的 `beforeunload` 框没人应答，渲染进程停在等应答态，
     脚本前一步还好好的、某一步之后**整片命令超时**。域状态是**连接级**的：同一浏览器上别的
     连接 enable 过，本连接也可能「看起来能收框」—— 时灵时不灵的假象。

  2. **`Page.reload` 不能用来复位脏页**：脏页上它**同样会弹框**（`Page.enable` 后可见
     `dialogOpening type=beforeunload`），但被 accept 时**导航被取消** —— `Page.reload` 7ms 返回、
     `frameNavigated` 0 次、`window` 标记不变、标签仍是脏的（取证脚本 `tmp-reload-dialog-probe.mjs`
     跑完即删；第十一轮的 `setText` 回读判据也是为「假重载」这类坑设的）。
     复位的正确手段 = `rebuildTab()` 换标签页（harness / 批跑器本来就这么做）。
     会真的走完导航的是**页面内发起**的导航（`location.reload()`），故自检用例 ② 用它造框。
     （此条先前一度被写成「`Page.reload` 绕过 beforeunload 检查」，属未复现的猜测，已按实测改正。）
