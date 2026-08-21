# 03 — 顶栏合并 + 全量回归验证

**要做什么：** header 与 nav 合并为一条紧凑顶栏（减少垂直占用），并对全部改动做最终回归：无头 Edge 截图对比、js 抽取测试、契约钉测试、全量 pytest。

**被谁阻塞：** 01 视觉打磨、02 步骤导航。

**状态：** ready-for-agent

- [ ] header + nav 合并为一行：品牌 + 流程链（窄屏隐藏流程链）+ 8 个 tab 同排
- [ ] 合并后导航 tab 样式与新顶栏协调（激活态保留青色下划线或胶囊）
- [ ] 无头 Edge 1440 宽截图：生成页顶部 / 模块库 / 赛题库，与改动前对比无明显回归（文字截断、错位、颜色冲突）
- [ ] `node tests/js/*.test.mjs` 全绿
- [ ] `pytest tests/test_generate_check_contract.py` 全绿
- [ ] 全量 pytest 一次通过
