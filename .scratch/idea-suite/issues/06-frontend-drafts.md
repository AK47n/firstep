# 工单 06：想法草稿箱前端 UI（fx/task.js + ui/generate-tasks.js + index.html + 测试）

Status: resolved

> 修订说明（双轴评审）：tasksIdeaAnalyze 增加返回契约 true/false（批量循环
> 据此失败即停——catch 不回抛的既有语义不动）；单条分析/批量/增删的互斥
> 守卫统一（增删走 tasksSetBusy 共享 tasks.busy 闸；批量经 draftState.busy
> 禁草稿按钮）；tasksDraftsLoad 挂 tasksReload 成功路径（草稿区无折叠交互，
> 按目录加载读回，首次进入已覆盖）。

## 目标

实现 spec 第 7-8 条用户故事前端：想法输入区「存入草稿」+ 草稿区列表（分析这条 / 删除 / 全部逐条分析，状态行 第 N/总）。

## 交付

- **fx/task.js**（纯函数 + esc + window 桥 + fx-guard 登记）：
  - `ideaDraftListHTML(drafts, opts)`：逐条 = 文本（截断展示 + title 全文）+「分析这条」（data-draft-action="analyze"）+「删除」（data-draft-action="delete"）；底部「全部逐条分析」（data-draft-action="all"）；空列表 → 引导文案；opts.busy → 按钮禁用。
- **ui/generate-tasks.js**：
  - `draftState{busy, drafts}`；`tasksDraftsLoad`（/chat/…/drafts/read）在展开草稿区时调用；`tasksDraftAdd`（输入区「存入草稿」按钮 → POST add）；`tasksDraftAnalyze(text)`（= tasksIdeaAnalyze(text) 复用）；`tasksDraftDelete(id)`；`tasksDraftAnalyzeAll`（顺序逐条循环，状态行「分析中 第 N/总：<标题>」，每条间 await；busy 守卫）。
  - 委托 data-draft-action；跨簇重置清草稿状态。
- **index.html**：想法输入区加「存入草稿」按钮 + 草稿区容器（#tasks-drafts + #tasks-drafts-status）+ CSS（.draft-item 等，沿用变量）。
- 测试：task.test.mjs 新用例（列表渲染/空态/按钮 data 属性/转义）；fx-guard 登记新导出；JS 全量绿。

## 验收

1. 「存入草稿」：输入框内容进草稿并落盘；输入框清空；重复存入同文本不新增。
2. 草稿列表：每条「分析这条」触发分析流程（结果卡正常）；「删除」即时移除并落盘。
3. 「全部逐条分析」：状态行显示进度，逐条分析完成后结果卡为最后一条；中断（busy）后按钮恢复可重试。
4. 全部 JS 测试绿（既有 559 + 新增）。
