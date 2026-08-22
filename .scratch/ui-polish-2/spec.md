# Spec：步骤导航升级为胶囊标签（ui-polish-2）

> 延续 ui-polish（01/02/03 已完成）的迭代。用户已确认只做方向 A。

## 问题陈述

生成页左侧步骤导航（工单 ui-polish/02）目前是 46px 宽的纯圆点列：12 个圆点只有数字，步骤名要靠浏览器 title 悬停才看得到。长流程里「第 7 步是什么」必须悬停或滚动对照卡片，可读性差。

## 方案

把左侧导航从「圆点列」升级为「胶囊标签列」：

- 每项结构：`[圆点 n] 步骤名`，横排胶囊，宽约 150px；
- 12 步步骤名常显（不再依赖 title 悬停）；
- 状态配色沿用现有令牌：
  - 默认：圆点灰底描边 + 数字，标签 muted；
  - hover：圆点青色描边微光，标签提亮；
  - 当前步（滚动高亮）：圆点青色渐变填充，标签 `--text` 亮色；
  - 已完成：圆点绿色渐变填充 + ✓，标签绿色调（沿用现有绿）；
- 交互不变：点击平滑滚动到对应卡片、滚动高亮当前步、markStepDone/Undone 联动卡片徽章——全部复用现有逻辑与纯函数（`stepNavTitles` / `stepNavCurrent`）；
- 窄屏规则不变：<1180px 隐藏整个导航。

## 实现决策

- 只改 `src/contest_generator/static/index.html` 与 `tests/js/step-nav.test.mjs`；后端零改动、API 契约零改动。
- `stepNavDotsHTML` 更名为 `stepNavItemsHTML`（输出胶囊结构：`<button class="step-dot" data-step="n"><span class="dot">n</span><span class="label">步骤名</span></button>`），`tests/js/step-nav.test.mjs` 同步改名与断言（该测试为本迭代新增，属可演进测试缝；被抽取函数名须与测试一致）。
- `markStepDone/Undone` 改为操作内部 `.dot` span（textContent 置 ✓ / 数字），不再整按钮替换；`.step-dot.done` / `.step-dot.current` 状态类名不变。
- 步骤名带引号等特殊字符时沿用现有 `&quot;` 转义逻辑（纯函数内联，不依赖页面 `esc`）。
- 视觉回归：无头 Edge + CDP 截图（1440 宽顶部 / 滚动中段）+ 计算样式断言（导航可见、胶囊宽度、done 步 ✓）。

## 测试决策

- 更新 `tests/js/step-nav.test.mjs`：抽取 `stepNavItemsHTML`，断言胶囊结构与标题转义；`stepNavTitles` / `stepNavCurrent` 测试不变（函数未动）。
- `node tests/js/*.test.mjs` + `pytest tests/test_generate_check_contract.py` 全绿；全量 pytest 后台跑一次保底。

## 范围外

- 不改 12 步卡片本体、不改 markStepDone 的信号点、不改窄屏隐藏规则。
- 不做其它方向（B 折叠 / C 进度条 / D toast / E 草稿 / F 细节包）——用户未选。
