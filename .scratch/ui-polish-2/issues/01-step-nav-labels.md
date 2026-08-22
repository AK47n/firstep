# 01 — 步骤导航升级为胶囊标签

**要做什么：** 生成页左侧步骤导航从「46px 纯圆点列」升级为「圆点 + 步骤名常显」的胶囊标签列（宽约 150px），状态配色沿用现有令牌；交互与完成联动全部复用现有逻辑。

**被谁阻塞：** 无——ui-polish/02 已提供导航骨架与信号点。

**状态：** resolved

- [x] CSS：`.step-nav` 加宽为胶囊列；`.step-dot` 改为 flex 行（内部 `.dot` 圆点 + `.label` 步骤名）；default / hover / current / done 四态配色
- [x] JS：`stepNavDotsHTML` → `stepNavItemsHTML`（输出胶囊结构，保留 `&quot;` 转义，超长标题 12 字截断 + title 全文兜底）；`markStepDone/Undone` 改操作内部 `.dot`；init 构建与滚动高亮逻辑复用
- [x] `tests/js/step-nav.test.mjs`：抽取 `stepNavItemsHTML` 并断言胶囊结构 / 截断 / 转义；`stepNavTitles` / `stepNavCurrent` 测试保持
- [x] 无头 Edge + CDP 验证：1440 宽截图目检（done ✓ 绿 / current 青 / 常态灰）+ 计算样式断言（nav 宽 158px、12 项、done/current/undone 状态、label 截断与 title 全文）
- [x] `node tests/js/*.test.mjs`（57/57）+ `pytest tests/test_generate_check_contract.py`（50/50）全绿
- [x] 全量 pytest 一次通过（2126 passed, 0 failed）
