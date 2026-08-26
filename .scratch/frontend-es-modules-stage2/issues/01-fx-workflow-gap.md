# 01 — 阶段 1 补漏：fx/workflow.js（5 个被测试纯函数）

**要做什么：** 阶段 1 规划漏项收口。`tests/js/recent-workflows-format.test.mjs` 仍用正则抽取（非贪婪 `\n\}` 脆变体）wfNum / formatWorkflowUsage / formatWorkflowCost / formatWorkflowSummary / formatWorkflowCall（index.html 8228-8286 行区，5 个被测试纯函数，不在 fx-guard DOMAINS 表内）——迁入新建 `static/js/fx/workflow.js`，测试改 import，DOMAINS 登记 5 名，删除 index.html 定义。完成后 45 个 .test.mjs 全部直接 import（零字符串提取）。

**被谁阻塞：** 无（本票不依赖任何阶段 2 模块；git 确认 504a11c 引入，属阶段 1 工单 08 清单漏项）

**状态：** resolved（2026-08-27；JS 435 全绿（416 + 19 护栏）、pytest 2465 全绿、diag 零 EXC（favicon 404 既有噪音）、smoke 11/11、探针 01 通过）

## 实施记录

- 数字修正：工单正文「8228-8287 行区」系初稿估计，实际定义块 = 8228-8286（5 函数，59 行）+ 区段注释 8225-8227 + 空行 8287，整块删除 63 行 → 5 行注释（「已迁至 static/js/fx/workflow.js（阶段 2 工单 01）」）。
- fx/workflow.js：5 函数逐字搬移（docstring 全保留：formatWorkflowCost 的「估算参考值 / 节省 >0.005 才显示」契约注释）；域内常量无；无共享件依赖；尾部 window 桥 5 名（探针实测 typeof 均 function）。
- index.html：主体 module 顶部 import 行追加（settings.js 之后，**最小化**——仅 import 胶水实际引用的 formatWorkflowCall / formatWorkflowSummary；wfNum/usage/cost 三名为模块内部互引，不入主体 import）；`wfNum` 等 5 名 grep 零残留（无 `function <名>(` 定义）。
- 测试改造：recent-workflows-format.test.mjs 删 extract()/new Function 工厂（原注释「依赖顺序」一并删除），改 import 直测；**html 读入保留**——尾部「仪表盘文案」（服务商上报/估算参考值/官方账单为准/仅保存在内存/recent 端点）与「推荐缓存」（set-recommend-cache/cache_hit/复用本地推荐缓存）两段静态断言钉 markup 脚注与推荐事件接线，字符串经 grep 确认仍在 index.html（markup 2198/2201/2186/2754 + 调用点 8315），断言语义零变化。
- fx-guard.test.mjs：DOMAINS 新增 workflow.js 块（5 名 fn），护栏测试 18→19；435 = 416 + 19。
- 删除脚本纪律：.scratch/frontend-es-modules-stage2/apply-01.mjs（CRLF 感知、内容锚定 + 三处边界校验；首跑因「注释块后直接函数、无空行」的边界假设错误抛错——修正为「cIdx+1 为 dash 收尾 + cIdx+2 为 wfNum」后一次通过，文件未写坏）。
- 探针：probe-01-workflow.mjs（CDP 9251）：window 桥 5 名 function ✓；设置 tab 分发器切页 → loadRecentWorkflows 实况渲染（empty-state 155 字符，import 链无 ReferenceError）✓。

- [x] 新建 `static/js/fx/workflow.js`：wfNum / formatWorkflowUsage / formatWorkflowCost / formatWorkflowSummary / formatWorkflowCall 逐字搬移（docstring 全保留）+ 尾部 window 同名桥；无共享件依赖
- [x] index.html：删除 5 个定义（8225-8287 块），替换为「已迁至 static/js/fx/workflow.js（阶段 2 工单 01）」注释；主体 module 顶部 import 行追加（最小化：仅 formatWorkflowCall / formatWorkflowSummary）
- [x] tests/js/recent-workflows-format.test.mjs：删 html 读入（保留）+ extract() + new Function 工厂，改 import（fx/workflow.js）；断言语义不动（尾部两段静态断言保留 html）
- [x] tests/js/fx-guard.test.mjs：DOMAINS 登记 5 名（wfNum / formatWorkflowUsage / formatWorkflowCost / formatWorkflowSummary / formatWorkflowCall）
- [x] `node --test "tests/js/*.test.mjs"` 435 全绿（416 + 19 护栏）；pytest 2465 全绿
- [x] diag.mjs 零 EXC（favicon 404 为既有噪音）；smoke.mjs 11/11；探针 probe-01-workflow.mjs 通过
- [x] grep 零残留：index.html 无 `function wfNum(` 等 5 名定义
- [x] 中文提交 + CHANGELOG 记录

## 风险点（已消解）

- 测试文件的「正则抽取」移除后无依赖顺序断言遗留（原 ns 工厂仅 5 函数互引，import 直测覆盖）。
- 5 函数无模块级常量引用（grep 确认），无需随迁常量。
