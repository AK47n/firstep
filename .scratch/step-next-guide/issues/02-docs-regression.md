# 02 — 文档与回归：CONTEXT.md 词条 + 全量测试

**要做什么：** CONTEXT.md 任务推进行补充「下一步引导」（做完一步当前卡提示下一步 + 滚动高亮下一张待执行卡；纯前端）；全量回归（JS 全量 + pytest 全量确认无后端影响）+ 提交。

**被谁阻塞：** 01。

**状态：** resolved

**实现要点：**
- [x] CONTEXT.md：任务推进段补一句「做完一步自动引导下一步」（工单 step-next-guide/01：执行/反馈轮 done 后，当前卡显示『下一步 → tN：标题』并滚动高亮下一张待执行卡（pending/failed；纯前端瞬态，不落盘）」。
- [x] 全量 `node --test tests/js/*.test.mjs` 绿（544）。
- [x] 全量 pytest 绿（2646 passed，3 warnings）。
- [x] 提交（中文提交信息；含 spec/issues 随工单提交惯例；探针留 .scratch 不提交）。

**答复：** 已完成。
