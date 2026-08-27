# 工单 04：前端纯函数 + localStorage 记忆（fx/recommend.js 扩展）

> 来源：.scratch/buy-discuss/spec.md §2.3（§五 测试决策）
> 状态：resolved（双轴评审通过 + 整改：Standards 5 项 / Spec 3 项，E2E 10/10）

**要做什么：**
- `static/js/fx/recommend.js` 扩展纯函数（无 DOM/fetch，node 可测）：
  - `decisionBadgeHTML(decision)`：「✓ 已定」徽标（wordlist = 方案名；custom = 「已定·自定」）。
  - `reviewBadgeHTML(review)`：AI 审核三态徽标（feasible 绿 / risky 黄 / infeasible 红）+ reason 文本。
  - `discussionAreaHTML(s)`：对话区（历史消息列表 + 输入框骨架 + 「和 AI 商量」按钮位）——纯渲染，行为在 ui 层。
  - `decisionPayload(decision)`：上行载荷形状（{source, name, note, verdict?}）。
- localStorage 纯函数（draft-memory 先例的读写分离）：`loadBuyDecisions()` / `saveBuyDecisions(map)` / `matchBuyDecision(decisions, key)`——键 = suggestion 的 `name + category`（或降级名）；读写容错（JSON 坏 = 空，不炸）。
- 徽标共存规则：已定 + 推荐 + AI 建议三徽标可共存（已定优先渲染在行首）。

**被谁阻塞：** 无（纯函数层，可先做）。

**验收标准：**
- [x] 纯函数单测（徽标三态/共存、对话区渲染、payload 形状、localStorage 读坏容错）
- [x] fx-guard DOMAINS 登记新函数
- [x] tests/js 全绿；中文 commit（工单 04）
