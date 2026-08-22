# 01 — 草稿自动记忆（localStorage）

**要做什么：** 生成页表单态（题面 / 历史题号 / 平台 / 模块 / main.c / Q&A）自动存入 localStorage，刷新后恢复并联动步骤完成态；提供清除入口；读取损坏数据静默降级。

**被谁阻塞：** 无。

**状态：** resolved

- [x] 纯函数：`draftState`（组装可存对象）/ `draftSave(storage, state)` / `draftLoad(storage)`（损坏 JSON try/catch 兜底，自包含不依赖其它函数）/ `draftRestoreMeta(json)`（字段校验 + 裁剪，拒绝数组）
- [x] 写入钩子：problem / topic-id / main-c / qa-text input 防抖 400ms、平台选定、模块增删（renderSelected 内）
- [x] 恢复：init 完成后回填表单 + 按内容标记步骤完成（题面 → 1；平台有效 → 3；模块 → 6；main.c → 8）
- [x] 清除入口：恢复提示条「清除草稿」按钮 + 设置页「清除草稿」按钮（均带「已清除」反馈）
- [x] `tests/js/draft-memory.test.mjs`：假 storage 用例（存取往返 / 损坏 JSON / 抛错降级 / 非法字段裁剪 / 非对象拒绝 / setItem 抛错）8 个，全绿
- [x] E2E（CDP）：填写 → localStorage 落盘 → reload → 恢复（题面/平台卡/步骤 1/3/6 done/tip 显示）→ 清除成功；截图目检通过
