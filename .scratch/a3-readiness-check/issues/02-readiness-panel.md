# 02 「检查能否生成」按钮与检查单面板

> 归属 spec：`.scratch/a3-readiness-check/spec.md`

Status: resolved

## 背景

判据纯函数与 btn-generate 同源改造在工单 01 完成（`generateReadinessChecks` / `readinessSoftChecks` / `readinessRowHTML` / `readinessRowsHTML` / `readinessState`）。本工单做展示与交互。

## 任务

- 第 9 步卡（index.html 1108-1111）「生成工程」旁新增 `<button id="btn-readiness-check" data-ico="check">检查能否生成</button>`；按钮行下方新增 `<div id="readiness-check" class="hidden"></div>`。
- 新增 CSS（插在 `.card-step-status` 块后，~770 行）：`.rc-panel`、`.rc-row`（✅ 绿 / ❌ 红 / ⚠ 黄，状态图标 + 标题 + reason + 动作按钮）、`.rc-go` / `.rc-recommend` 按钮样式，复用现有令牌与 `.item` 排版风格。
- 新增 `renderReadinessPanel()` / `refreshReadinessPanel()` / `initReadinessCheck()`：见 spec 实现决策 6-8；点击 `#btn-readiness-check` 展开/收起 + 渲染；容器事件委托 `.rc-go`（scrollIntoView smooth）+ `.rc-recommend`（题面守卫 + `recommendClarifications=[]` + `startRecommend(problem)`）。
- `syncStepDone` 中 `refreshGenOverview()` 旁追加 `refreshReadinessPanel()`；`initReadinessCheck()` 调用加在文件尾 `initGenOverview()` 之后。
- 面板重新打开时应反映最新状态（每次点击都重渲染）。

## 验收标准

- [x] 点击「检查能否生成」展开检查单：硬 4 项各带 ✅/❌ + 原因，❌ 行带「去第 N 步」；缺模块且已填题面时带「一键跑推荐」
- [x] 软条件 5/8 以 ⚠ 展示（5 仅在模块非空时出现）
- [x] 「去第 N 步」点击后平滑滚动到对应卡片
- [x] 「一键跑推荐」与「让 AI 推荐」按钮行为一致（同一 `startRecommend` 入口；题面空则跳到第 1 步）
- [x] 推荐完成后检查单自动刷新（markStepDone(5/6) 路径联动）
- [x] headless Chrome 实测：初始 0 就绪 → 检查单正确；markStepDone(1/3/6) + 填 main-c 后再查 → 全部 ✅/⚠ 状态正确；截图目检无溢出
- [x] `node --test "tests/js/*.test.mjs"` 全绿；pytest 语言/编码套件通过
