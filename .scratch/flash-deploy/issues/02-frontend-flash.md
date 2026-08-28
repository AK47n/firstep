# 02 — 前端：烧录按钮 + 结果展示 + 工具缺失指引 + 设置项

**要做什么：** 生成结果面板与任务执行结果面板各加「烧录到板子」按钮；点击防重 + 「烧录中…（XDS110/ST-Link，请确认连接）」状态；结果行（✓ 已烧录 / ✗ 输出尾 / 工具缺失指引卡：安装说明 + 设置页路径 + 复制烧录命令）；设置页三路径输入项（自动探测到显示「已自动找到」）。

**被谁阻塞：** 01 — 后端烧录模块与 /api/flash。

**状态：** pending

- [ ] fx 纯函数（fx/flash.js 或并入既有 fx）：命令展示/指引文案/结果徽章（ok/fail/no-tool 三分支），js 测试断言。
- [ ] 任务执行结果面板（ui/generate-tasks.js tasksRenderResult）插烧录按钮 + 烧录中/结果行（后端 busy 防重）；生成结果面板（generate-core 结果区）同款。
- [ ] 工具缺失指引卡：平台对应安装（OpenOCD/st-flash / DSLite 已带）+ 设置页跳转 + 一键复制命令；产物缺失提示「请先完成编译」。
- [ ] 设置页（ui/settings.js + index.html）：openocd_path / stflash_path / dslite_path 三输入 + 自动探测状态提示；测试（settings 保存/读回）。
- [ ] JS 全量测试绿 + review。

**答复：** （实现后填）
