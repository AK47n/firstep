# 11 — 收尾：防回退护栏 + 词表 + 全量双绿

**要做什么：** 阶段 1 的收尾切块：一张结构护栏测试令「已搬函数双源回退」不可能发生；CONTEXT.md 词表记录模块化约定；全量回归（JS 416 + pytest）与真浏览器冒烟确认。

**被谁阻塞：** 02-10 全部

**状态：** ready-for-agent

- [ ] 新建 tests/js/fx-guard.test.mjs：枚举全部已搬函数名（esc / formatSize + 各域），断言 index.html 不含 `function <name>(` 定义（防双源回退；由已迁 fx 模块 import 断言其存在）
- [ ] CONTEXT.md「架构要点」新增前端模块化 bullet：纯函数单源在 static/js/fx/*.js（0 构建、window 同名惰性桥、DOM 胶水仍在 index.html 属阶段 2 迁移对象）
- [ ] `node --test "tests/js/*.test.mjs"` 416 全绿；pytest 全绿
- [ ] 浏览器冒烟：全部 8 个 tab 正常（生成流程走一次到骨架生成前）
- [ ] 提交（中文信息）与 CHANGELOG 记录
