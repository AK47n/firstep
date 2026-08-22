# 03 — 细节打磨包

**要做什么：** 滚动条美化、spinner 统一与降级、禁用态视觉、按钮内 spinner 对齐。

**被谁阻塞：** 无。

**状态：** resolved

- [x] WebKit 滚动条美化——已存在（L411-417：`::-webkit-scrollbar` 细条圆角 + `scrollbar-width: thin` + `scrollbar-color`，变量驱动亮暗自适应），无新增
- [x] `.spinner` 动效降级：`@media (prefers-reduced-motion: reduce)` 关动画（**须在 .spinner 定义之后，否则级联被后面的 `animation: spin` 覆盖**——首版放按钮区被 L300 覆盖，已移到 @keyframes spin 后）；`button .spinner { vertical-align: middle }` 按钮内对齐
- [x] 禁用态统一：`textarea/input/select:disabled { opacity: .6 }`（补输入类缺失）+ `button:disabled:hover` 不再响应悬停（保持默认边框/文字色）
- [x] CDP 验证：disabled textarea opacity=0.6、disabled button 无 accent 边框、reduced-motion 下 spinner animation=none（正常时 spin）、按钮内 spinner vertical-align=middle
- [x] 全量测试（js 84/84、契约 50/50）
