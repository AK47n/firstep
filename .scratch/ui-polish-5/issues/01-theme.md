# 01 — 亮色主题切换

**要做什么：** `html[data-theme="light"]` 亮色变量覆盖 + 顶栏切换按钮（🌙/☀️）+ localStorage 记忆 + 引脚 SVG 硬编码色变量化。

**被谁阻塞：** 无。

**状态：** resolved

- [x] CSS：`html[data-theme="light"]` 覆盖全部颜色变量（GitHub 亮色系）+ `color-scheme: light` + `--pin-pad/--pin-pcb` 亮色适配 + body 背景/文字过渡
- [x] 顶栏主题切换按钮（🌙/☀️），点击切换；`applyTheme/currentTheme/initTheme`；localStorage `firstep.theme`；head 内联脚本防闪烁（CSS 应用前设 data-theme）
- [x] 引脚板图 SVG `fill="#0d1117"`（2 处）→ `fill="var(--bg)"`
- [x] CDP 验证：dark→light→dark 切换、body 背景 rgb(13,17,23)→rgb(246,248,250)、刷新保持 light、清除偏好回 dark；亮色全页截图目检（对比度正常、青色强调清晰、无深浅混叠）
- [x] 全量测试（js 76/76、契约 50/50）
