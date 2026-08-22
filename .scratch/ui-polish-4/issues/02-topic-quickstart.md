# 02 — 赛题库「用此题生成」一键跳转

**要做什么：** 赛题库列表每行加「用此题生成」按钮：取题面 → 填生成页 → 步 1 完成 → 切 tab + 滚顶 → toast。

**被谁阻塞：** 无。

**状态：** resolved

- [x] loadTopics 行模板加 `data-topic-use` 按钮 + 事件绑定（与删除按钮同列）
- [x] `useTopic(key)`：复用 `/api/topics/:key` 端点，填入题面 / currentTopicId / clearTopicSummary / markStepDone(1) / toast / 切生成 tab / 滚顶
- [x] CDP 验证：8 行按钮存在；点击后生成页激活、题面「C 题：无线充电电动小车（本科）」填充、步 1 done、toast 出现；截图目检通过
- [x] 全量测试
