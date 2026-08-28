# 02 — 前端：烧录按钮 + 结果展示 + 工具缺失指引 + 设置项

**要做什么：** 生成结果面板与任务执行结果面板各加「烧录到板子」按钮；点击防重 + 「烧录中…（XDS110/ST-Link，请确认连接）」状态；结果行（✓ 已烧录 / ✗ 输出尾 / 工具缺失指引卡：安装说明 + 设置页路径 + 复制烧录命令）；设置页三路径输入项（自动探测到显示「已自动找到」）。

**被谁阻塞：** 01 — 后端烧录模块与 /api/flash。

**状态：** resolved

- [x] fx 纯函数（fx/flash.js）：flashBusyText / flashResultHTML（ok/fail 两分支 + 输出明细 + 命令复制）/ flashGuideHTML（指引卡 + 设置页跳转按钮）/ flashOutputHTML / flashCommandHTML / flashPanelHTML（任务结果面板控制行），js 测试断言（tests/js/flash.test.mjs 9 条）。
- [x] 任务执行结果面板（ui/generate-tasks.js tasksRenderResult）插烧录按钮 + 烧录中/结果行（busy 防重 = tasks.busy 全局闸）；生成结果面板（generate-core 结果区）同款（busy 防重 = btn.disabled）；执行体共享 ui/flash.js flashRunShared（评审整改：两簇同构抽取）。
- [x] 工具缺失指引卡：flashGuideHTML = 平台安装说明（后端 message）+ 设置页跳转按钮（btn-flash-goto-settings）+ 产物缺失提示「请先完成编译」；一键复制命令在结果卡 flashCommandHTML（成功/失败均有真实命令；工具缺失 400 无 command_text——参考命令内嵌 message 文本，刻意不改 400 错误契约）。
- [x] 设置页（ui/settings.js + index.html）：openocd_path / stflash_path / dslite_path 三输入 + 「已自动找到」状态行（后端 settings GET flash_auto_tools 探测 + 前端 flashAutoStatus 渲染）；测试 = tests/test_flash.py test_flash_settings_roundtrip + test_flash_settings_auto_tools_*（后端 PUT/GET 读回）。
- [x] JS 全量测试绿（540）+ 双轴 review + 整改复核。

**答复：** 已实现并合入（提交见 git log flash-deploy/02）。整改说明（两轮评审）：①spec 缺口「已自动找到」→ 后端 _flash_auto_tools + 前端状态行；②spec 缺口「指引卡设置页跳转」→ flashGuideHTML 渲染按钮（原 handler 死代码）；复制命令偏差 = 工具缺失 400 只带 message（FastAPI detail 字符串契约），参考命令内嵌 message 可手动复制，刻意保持；③spec 缺口 settings 测试 → 后端 roundtrip 测试（前端为胶水无单测先例）；standards 判断项：控制行抽 fx/flashPanelHTML、两簇同构抽 ui/flash.flashRunShared、data-dir 死属性改委托回读、tasksRender 冗余 stale.remove 删除；④超范围但必要：结果面板插入 afterend→beforeend（beforeend 修复回滚按钮原死域委托——结果面板是网格兄弟节点不冒泡过网格，烧录按钮可用性依赖此修复）。
