# 工单 02：取题面 PDF 渲染期先露文字版的跳变不美观

- Status: resolved
- 依赖：无

## 现象（用户报告）

点击「取题面」后，题面文字版立刻显示，而原题 PDF 页图要几秒才渲染出来，
期间「先文字、后页图」的切换跳变不美观。

## 根因

`src/contest_generator/static/index.html`：

- `btn-topic-load` 点击处理器（约 1694 行）写入题面文本后调用 `loadTopicPdf(key)`；
- `loadTopicPdf`（约 1752 行）`await apiGet("/api/topics/{key}/pages")` 渲染 PDF 页图
  （数秒），成功后才 `showTopicPdfViewer`；
- 此前 textarea 文字版一直显示（`topicPdfTextVisible = true`），直到页图到达才
  `setTopicPdfTextVisible(false)` 强制收起 —— 形成「先露文字、再弹页图」的跳变。

## 方案

1. `loadTopicPdf` 一开始就显示 `topic-pdf-box` + 占位提示（empty-state：📄 渲染中…，
   提示可点「显示文字版（可编辑）」），并 `setTopicPdfTextVisible(false)` 收起文字版
   （渲染期不先露文字）。
2. `showTopicPdfViewer` 去掉强制 `setTopicPdfTextVisible(false)`：正常路径加载期已收起
   （页图到后保持收起 = 默认展示 PDF）；若用户在渲染期手动打开了文字版，页图到达后
   尊重用户选择，不再强制收起。
3. 失败路径不变：`hideTopicPdfViewer()` 恢复文字版 + toast 错误提示（无原 PDF 的赛题
   文字版照常可用）。

## 验证

CDP 端到端（真实服务 + 2024H）：点击取题面后立即检查 —— box 可见、占位存在、
textarea 隐藏；数秒后 —— 占位消失、页图 img 出现、textarea 保持收起。

## 影响面

仅前端 static/index.html 两处函数；后端 /pages 端点零改动。
