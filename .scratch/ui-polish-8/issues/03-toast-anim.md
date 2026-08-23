# 工单 03：toast 动效升级

- Status: pending
- 依赖：无

## 目标

toast（成功/失败/信息）加入场滑入与离场淡出动画 + 类型左边框着色，提示更醒目。
行为契约（2.5s 自动移除、上限 3 条丢最旧、点击关闭、HTML 转义）保持不变。

## 实现

1. CSS：
   - `@keyframes toast-in`：`translateY(-6px) + opacity 0 → 0 + 1`，.18s ease-out；
   - `.toast` 加 `animation: toast-in .18s ease-out`；ok 左边框 3px `var(--ok)`、
     error `var(--danger)`、info `var(--accent)`；背景微染对应 `-dim` 色；
   - `.toast-out`：`opacity 0 + translateX(6px)` 过渡 .18s；
   - prefers-reduced-motion：无动画、无过渡，直接显示/移除。
2. JS（toast 函数内改造，保持可抽取自包含）：
   - 移除流程：先加 `.toast-out`，`setTimeout(…, 180)` 后真正 remove 并
     解除点击监听；移除后重排 `#toast-root` 子节点位置（现有上限 3 逻辑复用）。
   - 自动移除计时（2.5s）不变；点击关闭走同一带离场动画的移除路径。
   - 现有转义（& < > " '）不变。
3. `#toast-root` 定位不变。

## 测试

- tests/js/toast.test.mjs（已有用例）行为断言不变（上限 3、转义、点击关闭、
  自动移除）；若断言依赖「立即移除」的 DOM 数量，改为断言先加 `.toast-out`
  再移除（或保留 setTimeout 由测试注入短时）。已有 8 用例尽量不改，
  新增 1 用例：移除前带 `.toast-out` 类。
- 契约测试不动。

## 验收

触发任一 toast：滑入出现、2.5s 后淡出移除；连续 4 条时最旧一条先离场；
类型左边框颜色正确；截图目检。
