# 25 — 清理：generate-mainc.js 滚动三同步抽取

**要做什么：** 评审 smell 清理（backlog 4.4 后半）——`generate-mainc.js` 滚动三同步在 `syncMainCHighlight` L29-30（hl.scrollTop/Left、nums.scrollTop）与 scroll 监听器 L36-39 内联重复 → 提 `syncPanels(ta)` 共享，两处改调用。仅内部重构零行为变化。

**被谁阻塞：** 无

**状态：** resolved（代码已于 f26e1fa 提交，2026-08-27 收尾时补翻状态）

## 验收标准

- [ ] `syncMainCHighlight` 与 scroll 监听器均改调 `syncPanels(ta)`；三行同步逻辑仅存一处
- [ ] node --test 全绿 + smoke 11/11（main.c 编辑器滚动实况：行号列/高亮层随动）
- [ ] 中文提交

## 实施记录

- 新增 `syncPanels(ta)`（含注记），syncMainCHighlight 尾部与 scroll 监听器均改调；三行滚动同步仅存一处。
- 全量 node --test 447/447；smoke 11/11（main.c 高亮 PASS）。
