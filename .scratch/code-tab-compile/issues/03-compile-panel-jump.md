# 03 — 代码栏编译按钮 + 底部错误面板 + 错误行跳转

**要做什么：** 状态栏加「编译」按钮 → 自动保存全部脏标签（02）→ POST /api/compile（只带 output_dir，平台自动推断=01）→ SSE 编译 → 编辑器下方底部可折叠面板：成功 = 状态行「编译通过 · N Error / N Warning · 耗时」，失败 = 错误列表自动展开（每条 `path:line` + 消息，点击打开文件并定位跳行）+ 「去生成页一键编译修复」引导（仅当前目录=生成上下文时显示，点击切生成页并滚到步骤 10）。

**被谁阻塞：** 01（平台推断）、02（保存全部）。

**状态：** resolved

**结论：** 已落地。状态栏「编译」按钮（重入保护从点击起含自动保存阶段）→ saveAllDirtyTabs → POST /api/compile {output_dir}（平台后端推断）→ SSE → 底部可折叠面板（状态行 + 错误列表 + 失败自动展开 + 「去生成页一键编译修复」仅目录=生成上下文显示）；错误行跳转 = ①/api/code/file 预检 → ②失败走 /api/compile/source-line 归一（UV4 形态验证）→ ③editJumpToFile 定位（评审按 spec 修正首试顺序）。文案单源 compileSummaryText（fx/generate.js，生成页横幅与面板共用）；isMainCDiskDir 单源（codeview 导出）。CDP 冒烟 17 项全 PASS + smoke-02/03/05 回归全绿；node 1001 全绿。

- [x] 验收 1：状态栏出现「编译」按钮；目录未打开时点击 → toast 中文提示。
- [x] 验收 2：点击编译 → 先保存全部脏标签（取消保存 → 中止编译并提示）；编译中按钮 disabled「编译中…」；完成恢复。
- [x] 验收 3：编译成功 → 面板显示成功状态行（含 N Error / N Warning / 耗时），面板可收起/清空。
- [x] 验收 4：编译失败 → 错误面板自动展开，列出 parsed_errors（path:line + message）；点击错误行 → 打开/激活对应 tab + 选区跳行（行高亮 + flash）；UV4 `..\` 形态路径经 source-line 归一后仍可打开（兜底链）。
- [x] 验收 5：平台推断失败 / 工具链缺失 → 400 中文进面板状态行 + toast。
- [x] 验收 6：「去生成页一键编译修复」仅当 codeDir = 生成上下文（isMainCDiskDir 判据）时显示；点击切生成页 + scrollToStep(10)。
- [x] 验收 7：新前端纯件挂 tests/js/code-compile.test.mjs（状态行/错误行渲染、面板状态机）；fx-guard 登记校验通过；node tests/js 全量绿 + smoke-02/03 回归绿（改动不破坏既有代码栏）。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
