# 03 — 裸装载退场：5 个"加载即接线"的模块给出显式 init()

**要做什么：** 修订簇 / 任务簇 / 参数簇 / 参数咨询 / 交付卡这 5 个模块（今天靠
`import "/js/ui/x.js"` 被加载才接线）各自导出一个显式 `init*()`，接线语句从求值期搬进去，
由 boot 显式调用；裸装载从清单里消失。"import 即接线"这条隐式边在这 5 个模块上退场。

**被谁阻塞：** 02（装载根搬家）

**状态：** resolved

> 评审与整改记录在两轴一起覆盖 03+04 的那一份里，见 `04-host-only-modules-get-init.md`
> 的 Comments「双轴评审整改」一节（结论：搬运逐字无损、绑定集合完全相同、判据 96→0；
> 9 条整改已落地）。

## 范围（实测清单见 spec「实现决策」）

| 模块 | 求值期副作用 |
|---|---|
| `ui/generate-revise.js` | 11 条（`analyzeCancel.onClick` / `execCancel.onClick` / 9 条 `$("btn-revise-*")`、`#revise-dir-input`、`#revise-problem-text` 绑定） |
| `ui/generate-tasks.js` | 24 条（`tasksCancel.onClick` / 20+ 条 `#btn-tasks-*` `#tasks-*` `document` 绑定 / 2 条 `window` 自定义事件） |
| `ui/params.js` | 7 条（`paramsCancel.onClick` / `#btn-params-scan` `#params-grid` `#params-result` / 2 条 `window`） |
| `ui/params-chat.js` | 7 条（`chatCancel.onClick` / `#btn-params-chat` `#params-chat` ×2 / 3 条 `window`） |
| `ui/delivery.js` | 5 条（首帧写 `#delivery-actions` / `bindDeliveryActions()` / 2 条 `window` / `Object.assign(window, …)` 挂桥） |

## 验收标准

- [ ] 5 个模块各导出显式 `init*()`（名字与既有导出不冲突，命名照各模块既有风格），
      上述列 0 副作用语句**逐条**搬进 init 函数体
- [ ] 被其它函数读的模块作用域声明（`analyzeAbort` / `chatCancel` / `tasksAbortSlot` 等）
      **留在原地**——只搬副作用，不搬声明（搬错 = 别处引用断）
- [ ] `ui/delivery.js` 的 `Object.assign(window, {...})` 随接线进 init：语义不变
      （仍在上线前装好；探针按全局名取用照旧），**不是**"顺手删桥"
- [ ] boot.js 里这 5 条裸装载换成具名 import ＋ 接线区显式调用，**调用顺序 = import 顺序**
- [ ] 判据自证：`boot-contract` 的"列 0 副作用"判据对这 5 个模块报 0 条（探针桥除外）
- [ ] 真浏览器冒烟（改前 / 改后各一次）：加载期监听器记账里这 5 个模块的绑定**逐条相同**
      （target + 事件类型都对得上）；`#delivery-actions` 仍被写；delivery 的 window 桥仍在；
      `#btn-params-chat` 真点击仍有行为反应；0 pageerror
- [ ] `node --test "tests/js/*.test.mjs"` 全绿、浏览器门禁 26 条全绿

## Comments

### 2026-09-21 实现记录

**5 个模块各得一个显式 init**（语句逐条搬进函数体，顺序 = 原文件先后顺序）：

| 模块 | init | 搬走的语句 |
|---|---|---|
| `ui/generate-revise.js` | `initRevise()` | 2 条取消按钮回调 + 11 条监听器 |
| `ui/generate-tasks.js` | `initTaskProgress()` | 1 条取消按钮回调 + 24 条监听器（尾部 281 行整块，脚本机械包裹 + 自校验"缩进复原后逐字相同"） |
| `ui/params.js` | `initParams()` | 1 + 7 条 |
| `ui/params-chat.js` | `initParamsChat()` | 1 + 7 条 |
| `ui/delivery.js` | `initDelivery()` | 5 条（含 window 兼容桥，语义不变） |

**boot.js**：5 条裸装载换成具名 import（顺序不动）＋ 正文最前新增**接线区**按 import 顺序显式
调用；顺带删掉 `"use strict";`（ESM 恒严格模式，冗余，且按"列 0 副作用"口径会被算成一条接线
——工单 02 评审指出）。

**判据自证**（`survey2.mjs` / `probe-01-red-proof.mjs`）：
- 11 个模块的求值期接线 **96 → 42 条**（少掉的 54 条正是这 5 个模块的）；这 5 个模块各自
  **0 条**；
- 判据③-a「零裸装载」：base 5 条红 → **工作树 0 条绿**；
- 判据③-b：11 个模块红 → **6 个模块红**（剩下的正是工单 04 的 6 个）；
- 登记表体检：8 红 → **3 红**（`generate-core` / `master` / `topic`，属工单 04）。

**真浏览器冒烟（改前 = HEAD（02 状态）/ 改后 = 本工单，同一支）**：`smoke-03-before.txt` /
`smoke-03-after.txt` —— **记账 434 条，排序后指纹两份同为 `4288323085`**（监听器的
**多重集完全一致**：target + 事件类型 + 条数），0 pageerror / 0 模块图链接错误、6 个 fx 探针桥
全在、5 个模块的接线全在、`#delivery-actions` 加载即写、`#btn-params-chat` 真点击有反应、
平台卡 / 步骤导航 / 总览 / 词表 / 检测卡读数一致。

**顺序（按设计位移，如实记账）**：接线区在 boot 正文最前 → 这 5 个模块的绑定从"import 求值期
（清单第 13–17 位）"挪到"所有 import 求值完之后"，因此它们在记账里的位置后移
（`#btn-revise-analyze#click` 52 → 124、`#btn-tasks-plan#click` 59 → 130、
`window#revise-context-loaded` 79 → 150），**集合与多重集不变**。这正是 spec「保序」一节的
明文约定（用监听器记账证明集合相同，边界顺序位移如实记录）。

**冒烟仪器自身的一个坑（本轮踩到并修掉）**：原先固定 `waitForTimeout(1500)` 等加载完成——
机器忙时**模块池最后那 171 条 checkbox 监听器**（`ui/generate-recommend.js:880`）会漏记，
读数出现"592 → 421"这种假差异（诊断脚本 `diag-listeners.mjs` 用调用栈定位到绑定点，实为
时序竞态，不是产品行为变化）。现在改成**确定性就绪信号**（等 `#platforms .platform-card`
与 `#module-grid > *` 都出现 + 300ms 收尾），两份读数稳定复现。

**门禁**：前端门禁 **1717 passed / 0 fail**（+1 = `import-usage-guard` 新增的"零裸装载"）；
浏览器门禁与 pytest 读数见下。
