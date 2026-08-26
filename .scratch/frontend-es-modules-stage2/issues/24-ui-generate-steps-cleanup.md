# 24 — 清理：generate-steps.js 重复监听器 + 弱命名

**要做什么：** 评审 smell 清理（backlog 4.4 前半 + 4.5），仅内部重构零行为变化：①`generate-steps.js:68-79` 「btn-clear-draft / btn-draft-clear」两个监听器 4 行逻辑逐字重复（clearDraft + 「已清除」→1.5s 还原「清除草稿」）→ 提 `bindClearDraftButton(btnId)` 共享；②`genOverviewWarn(n)`（L116）参数 `n` 为裸步骤号、名称不揭示语义 → 改名 `genOverviewWarn(stepNo)`（含 L129/140/158 调用处循环变量同步）；`overviewPlanNow(doneArr)` 参数名一并核（doneArr 尚可，若改名仅同步调用）。

**被谁阻塞：** 无

**状态：** resolved（代码已于 f26e1fa 提交，2026-08-27 收尾时补翻状态）

## 验收标准

- [ ] 共享 handler 抽取后两按钮行为逐字等价（点击→clearDraft→「已清除」→1.5s→「清除草稿」）
- [ ] 函数名/参数名语义化，调用点同步；无残留裸 `n` 步骤号参数
- [ ] node --test 全绿 + smoke 11/11（草稿清除按钮实况点按）
- [ ] 中文提交

## 实施记录

- L68-79 两监听器重构为 `bindClearDraftButton(btnId)` + 两行调用（行为逐字等价：clearDraft →「已清除」→1.5s→「清除草稿」）。
- `genOverviewWarn(n)` → `genOverviewWarn(stepNo)`（参数 + 体内两处引用；调用点传参不变）。overviewPlanNow(doneArr) 经核语义尚可，未改。
- 全量 node --test 447/447（含结构钉 step-done-refs 断言不涉）；smoke 11/11。
