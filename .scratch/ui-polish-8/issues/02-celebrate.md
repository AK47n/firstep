# 工单 02：步骤完成庆祝动画

- Status: resolved
- 依赖：无

## 目标

生成页 12 步流程里，某步完成时给视觉反馈：步骤徽章弹跳 + 卡片顶部青色光带扫过。
现在完成仅左侧胶囊圆点变绿 ✓，卡片本身无反应。

## 实现

1. 在 `markStepDone(n)` 成功路径尾部追加：给对应步骤卡加 `.celebrate` 类。
   卡定位：`#tab-generate .gen-steps > .card` 中 `.step-no` 文本 == n 的卡片
   （与 initStepNav 同口径；无卡片 = 跳过）。`.celebrate` 在 `animationend`
   后移除（一次性动画）。
2. `markStepUndone(n)` 同步移除 `.celebrate`。
3. 保持 markStepDone/Undone 现有行为（勾选胶囊 dot、进度条 stepDoneSet 等）
   逐字节不变；新增逻辑自包含（内联选择器字符串，不引模块级常量）。
4. CSS：
   - `@keyframes step-pop`：徽章 `scale(1) → scale(1.25) → scale(1)`，.35s；
   - `@keyframes card-glow`：卡片顶部 2px 青色渐变光带 `translateX(-100%) →
     100%`（0.6s），卡片 `position:relative` + `overflow:hidden`；
   - `.card.celebrate .step-no { animation: step-pop .35s ease; }`
     `.card.celebrate::before { animation: card-glow .6s ease .1s; }`
     （::before 为光带，默认 hidden）。
   - prefers-reduced-motion：动画禁用（光带直接不显示）。

## 测试

- tests/js/celebrate.test.mjs：markStepDone 抽取测试补充——伪 DOM 下
  `.celebrate` 类加/移除断言（与 step-nav 测试同构造）；undo 移除断言。
- 契约测试不动。

## 验收

完成任意步骤（如上传题面）→ 徽章弹跳 + 光带扫过一次；undo 后动画类消失；
截图目检。
