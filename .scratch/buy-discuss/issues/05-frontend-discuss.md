# 工单 05：前端对话交互 + 确定（ui/generate-recommend.js + index.html + E2E）

> 来源：.scratch/buy-discuss/spec.md §2.1-2.3
> 状态：resolved（双轴评审通过 + 整改：Standards 5 项 / Spec 3 项，E2E 10/10）

**要做什么：**
- `ui/generate-recommend.js`：选型参考面板底部「和 AI 商量」按钮 → 展开对话区（discussionAreaHTML 渲染）。
  - 发送：消息入 history → `POST /api/buy/discuss`（同步）→ 回复追加历史 + review 徽标渲染；busy 态（按钮禁用 + 转圈）；错误 toast/内联。
  - 轮数上限 8：第 8 轮后输入区变「总结并确定」提示（不可再发，防失控）。
  - 确定：词表方案行「就用这个」按钮 / 自定文本入口（输入后确定）→ decision 写 state + localStorage + 重渲染徽标。
  - 恢复：renderRecommendResult 渲染时按 `matchBuyDecision` 恢复 decision（localStorage 命中 → 徽标即现）；重推后建议名变了 → 恢复由「name+category」匹配（匹配不上 = 不恢复，不丢用户数据）。
- `index.html`：对话区/确定按钮样式（复用 item/chip/badge 风格，0 构建）；suggestion 渲染走 fx（无内联函数）。
- 上行：生成请求 payload 的 requirements 已带（前端把 suggestion.decision 并入——`generate-core.js` 或统一出口把 decision 序列化进 requirements 再 POST /api/generate）。
- E2E（拦截式浏览器实测）：讨论一轮（mock 端点）→ review 徽标 → 点「就用这个」→ ✓ 已定徽标 → localStorage 落键 → 刷新页面重开推荐（mock 同载荷）→ 徽标恢复 → 生成请求载荷含 decision。

**被谁阻塞：** 01-04。

**验收标准：**
- [x] 讨论一轮往返（mock）+ review 三态展示
- [x] 确定 → 徽标 + localStorage + 上行载荷（生成请求捕获断言）
- [x] 8 轮上限行为
- [x] 刷新恢复（localStorage）
- [x] tests/js 全绿 + 浏览器 E2E 全绿；中文 commit（工单 05）
