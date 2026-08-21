# 03 — 顶栏合并 + 全量回归验证

**要做什么：** header 与 nav 合并为一条紧凑顶栏（减少垂直占用），并对全部改动做最终回归：无头 Edge 截图对比、js 抽取测试、契约钉测试、全量 pytest。

**被谁阻塞：** 01 视觉打磨、02 步骤导航。

**状态：** resolved

- [x] header + nav 合并为一行：品牌 + 流程链（窄屏隐藏流程链）+ 8 个 tab 同排
- [x] 合并后导航 tab 样式与新顶栏协调（激活态保留青色下划线）
- [x] 无头 Edge 截图回归：1440 / 1000 / 770 三档宽度计算样式断言（`.sub`/`#step-nav` 显隐、tab 溢出、单行）+ 生成 / 模块库 / 赛题库三页目检，无回归
- [x] `node tests/js/*.test.mjs` 全绿（56/56）
- [x] `pytest tests/test_generate_check_contract.py` 全绿（50/50）
- [x] 全量 pytest 一次通过（2126 passed, 0 failed）
