# 03 — 双向跳转桥

**要做什么：** 生成成功结果区「下一步」与步骤 8 工具栏各加「在代码查看器中打开工程」→ 切到「代码」tab 并打开该工程目录；「代码」tab 正在查看的目录与生成上下文一致时，查看器顶栏出现「去生成页编辑 main.c」→ 切回生成页、滚动到步骤 8 并按用户主动点击加载磁盘 main.c 到编辑框。代码查看器维持只读，不新增编辑能力。

**被谁阻塞：** 01（生成上下文目录）。

**状态：** resolved

- [x] 生成成功后，结果区「下一步」出现「在代码查看器中打开工程」；点击后切到代码 tab 并展示该工程文件树。
- [x] 步骤 8 工具栏同按钮可用（仅存在生成上下文时显示；无上下文时隐藏）。
- [x] 代码 tab 打开的目录 === 生成上下文目录 → 顶栏显示「去生成页编辑 main.c」；打开其它目录 → 不显示。
- [x] 点击「去生成页编辑 main.c」→ 切回生成页、滚动到步骤 8、编辑框加载磁盘 main.c（加载是显式动作，不静默覆盖）。
- [x] 代码查看器内无新增编辑 / 写入入口。

## 实现说明

- 入口按钮：结果区「下一步」（btn-goto-code-result）+ 步骤 8 工具栏「查看工程」（btn-goto-code-mainc，title 全称）——两者 click 均 openCodeViewer(getMainCDiskDir())；openCodeViewer 保持导出桥（recent.js 先例）。
- 可见性联动：btn-goto-code-mainc 随磁盘语境显隐（generate-mainc-sync renderDiskState 统一驱动——生成成功/草稿恢复/最近记录回退/清空四处同源，无上下文时隐藏）。
- 代码 tab 侧：loadCodeDir 后 updateGotoGenerateVisibility（codeDir === getMainCDiskDir() 精确等值，无路径归一——两处来源同一字符串）；「去生成页编辑 main.c」click = 切 tab + scrollToStep(8) + loadDiskMainC()（与「从磁盘重新加载」同一加载路径，显式意图才覆盖）。
- 只读契约：代码 tab 零新增写侧（冒烟断言 tab 内无 textarea）。
- 验证：smoke-03.mjs 12 项（含可见性两态 + 目录匹配切换 + 加载回填 + 只读契约）；node --test 963 全绿。
- 备注：本机 recent.json 有历史记录 → 无草稿回退（工单 01）会先给上下文，冒烟先清空再断言（确定性）。
