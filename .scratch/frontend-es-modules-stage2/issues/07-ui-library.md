# 07 — 模块库 tab：static/js/ui/library.js

**要做什么：** 模块库 tab 全部 DOM 胶水迁入 `static/js/ui/library.js`（chips/stats/表格/过滤器/工具栏/加载/描述编辑/模块编辑弹窗/删除/新建载荷）；`state.modules` 属性写点随簇。**被谁阻塞：** 02（app.js）+ 06（files.js）+ **12（生成推荐簇 ui/generate-recommend.js + 步骤状态核心 ui/step-state.js）**

## ⚠ 工单序调整（2026-08-27，实施中发现）

library 簇有两个跨簇硬边：renderLibraryTable 的「详情」按键调 `openModuleInfo`、loadLibrary 成功路径调 `renderModulePool`——均为**生成推荐簇 A** 的函数（模块化前在 host，library 模块无法引用）。故本票**改挂在工单 12 之后**（12 交付 A + 步骤状态核心后，本票从 ui/generate-recommend.js import 两函数）。spec.md 已追加「工单序调整」小节。

**状态：** resolved（2026-08-27；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、probe-07 模块库实况 7/7）

## 实施记录

- **static/js/ui/library.js**（新建 ~460 行）：libUI 状态 + 11 函数逐字搬移（renderLibraryChips / renderLibraryStats / renderLibraryTable / clearLibraryFilter / initAddSections / initLibraryToolbar / loadLibrary / editDescription / editModule / deleteModule / newModulePayload）+ 添加模块表单侧接线（`$("btn-add-file-row")` 监听 + `addFileRow()` 初始行 + 两个 mod 文件选择绑定 + btn-draft-desc / btn-add-module-submit 监听）随簇。import app.js（含 state——属性写点 loadLibrary/editDescription/editModule 成功路径）/ fx/module.js（10 纯名）/ ui/files.js（addFileRow/collectFiles/pickFilesInto/bindFilePicker——跨簇共用件）/ **ui/generate-recommend.js（openModuleInfo + renderModulePool——工单序调整的核心硬边）**。export：loadLibrary / initLibraryToolbar / initAddSections / editModule / deleteModule / newModulePayload（host import 代理 + 收尾核对用）。
- **index.html（apply-07.mjs，7061→6655 行）**：①host import 行（library 6 名代理）+ generate-recommend 代理行**裁 openModuleInfo**（host 不再调用，唯一调用点随簇迁走）；②段 A（libUI → addFileRow() 初始行，含 06 注记与 btn-add-file-row）→注记；③段 B（选择文件注记 + 两个 mod 绑定）→一行注记（**ref 两个绑定留 host**——参考库簇 08 迁时带走）；④段 C（newModulePayload + btn-draft-desc / btn-add-module-submit）→注记。校验：11 函数 + libUI 零残留、host 保留 ref 绑定点与 loadLibrary/initLibraryToolbar/initAddSections 调用点、openModuleInfo 调用点零残留（随簇）。
- 验证：node --test 442 全绿（无新测试——本票纯胶水；fx 单源 fx-guard 亦绿）；pytest 2465 全绿（bg）；diag 零 EXC；smoke 11/11；probe-07.mjs 7/7（启动 init 完成 → 切 tab → loadLibrary 26 行 + 统计「共 26 个模块 · STM32 22 · MSPM0 26 · 已验证 25 · 硬件绑定 6 · 互斥组 2」+ chips → 详情弹窗（openModuleInfo 跨簇 import 实况：adc 详情文本）→ 模块池 26 卡联动 → lib-search 过滤回环 rows=2 → 初始文件行 1 + ref 绑定仍在 host → 零 EXC）。

## 检查表

- [x] 新建 `static/js/ui/library.js`：11 函数 + libUI + 表单接线逐字搬移 + import（app.js / fx/module.js / fx/core.js / ui/files.js / ui/generate-recommend.js）+ export + 头部注释（含状态写点说明：state.modules 属性写）
- [x] index.html：apply-07.mjs（CRLF 感知 3 段删除 + import 行 + 代理行裁 openModuleInfo）
- [x] `node --test` 442 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + probe-07 模块库实况 7/7
- [x] grep 零残留：index.html 无 11 函数定义 / 无 libUI / 无 openModuleInfo 调用点
- [x] 中文提交

## 风险点 / 跟踪

- **host import 代理 6 名**：loadLibrary（页签分发器 2267）/ initLibraryToolbar + initAddSections（启动区）/ editModule / deleteModule / newModulePayload（本票起 host 不再直接调用——收尾工单 20 统一核对裁代理）。
- **ref 两个 bindFilePicker 绑定点（btn-ref-pick-files / btn-ref-pick-dir）留 host**：参考库簇（08）迁时带走；届时 host 的 files.js 代理名裁减按 08 使用面核对（addFileRow/collectFiles/pickFilesInto 仍被参考簇使用）。
- **ui/library.js → ui/generate-recommend.js 单向 import**（openModuleInfo / renderModulePool）：generate-recommend 不 import library，无环；12 的 clusterDeps 接缝不受本票影响（library 不触 pin/draft 服务）。
- **无结构钉测试覆盖本簇**（tests/js 无 renderLibraryTable/libUI 等断言）——探针 probe-07 承担实况回归。
