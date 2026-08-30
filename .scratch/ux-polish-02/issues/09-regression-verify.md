# 09 — 回归验收（全量测试 + CDP 走查截图）

**要做什么：** 07 张改进包全部落地后的最终验收：全量前端 node:test + Python 测试保持全绿；用 CDP 走查脚本对关键行为截图确认（不发真实 LLM 请求）；确认 spec 中「范围外」项未被动到。

**被谁阻塞：** 01-08。

**状态：** resolved

**验收结果：** node --test "tests/js/*.test.mjs" 全绿（845 例）；pytest 全量 2877
passed（含中文兜底 test_repo_language.py；本轮附带修复 autocommit 读写函数登记
表：library.module_mtime / reference_library.entry_mtime 补 registered("read")）；
CDP 回归探针 probe-t09.mjs 全 PASS：01 完成态初始、02 折叠记忆刷新保持、03 横幅
定位展开聚焦、04 去任务推进自动加载（临时工程）、05 failed 无确认通过 + 跳过确认、
06 doing 阶段槽、08 mtime 排序自动降序、九页签无横向溢出、无 JS 异常、零真实
LLM 请求（recommend/execute/split 计数=0）。截图 shot-t09-{generate,library,tasks}.png
确认视觉（任务页 failed 卡无「确认通过」、模块库「排序：最近更新 ↓ 降序」）；
任务页截图需先回生成页再 goTaskProgress（子页签在生成页卡内，仅切子页签时顶层
页签不变——探针记录）。范围外项未动。

- [ ] `node --test "tests/js/*.test.mjs"` 全绿
- [ ] pytest 全量绿（含 test_repo_language.py 中文工单/spec 兜底）
- [ ] CDP 截图确认：空推荐不标步骤 5、默认布线「默认布线」标记、折叠初始态/记忆、横幅聚焦 key、去任务推进自动加载、failed 卡无「确认通过」、doing 卡阶段槽、库刷新/空态/统计提示
- [ ] 生成页/设置页/任务页/四库页面无 JS 异常、无横向溢出（1280 宽）
- [ ] 确认未触发任何真实 LLM 请求（无推荐/执行调用）
- [ ] CHANGELOG 中文条目由提交钩子自动补录；本轮提交信息中文

