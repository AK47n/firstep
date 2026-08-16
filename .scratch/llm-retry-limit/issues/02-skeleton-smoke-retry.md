# 02 — 骨架/冒烟 main.c 出稿接入重试原语

**What to build:** 用户指出骨架/冒烟出稿没有自动重试。把 `generate_main_skeleton` / `generate_smoke_main` 从单次 `_chat` 改为走 `_retry_parse`：空内容按解析类重试（快重试，上限 SUMMARY_RETRY_LIMIT），成功后行为与旧逐字节一致。

**Blocked by:** 01

**Status:** resolved（2026-08-15）

- [x] 两个方法用局部 parse 回调拒绝空白内容，失败经 _retry_parse 整次重问

## Comments

- 只拒绝空白内容；围栏剥离 / 未定义调用静态自检仍归 skeleton 管线（职责不变）。
- 成功路径行为逐字节不变（旧测试一次调用断言照旧通过）。
- [x] 成功路径测试零回归（一次调用即返回）
- [x] 新增空内容重试成功 / 耗尽大声失败测试（骨架 + 冒烟）
- [x] pytest 全绿 + mypy src 干净
