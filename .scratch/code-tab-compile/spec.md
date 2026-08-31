# 代码栏编译闭环（状态栏「编译」按钮 + 底部错误面板 + 错误行跳转）

> 会话/系列 slug：code-tab-compile。立项：2026-08-31（用户拍板，全部选推荐项）：
> ①编译入口 = 状态栏按钮 + 编辑区底部可折叠错误面板；②编译前自动保存全部脏标签
> （保存冲突弹既有冲突模态，处理完再编译）；③平台由后端从工程文件自动推断
> （/api/compile 的 platform 可省略）；④仅编译闭环——AI 修复仍在生成页修复中心
> （错误面板给「去生成页」引导），烧录按钮本轮不做。

## 问题陈述

「代码」tab 已升级为可看、可改、可存的 IDE 式编辑器（工单 code-viewer-editor
01~07g 全部落地），但「改完代码 → 验证」这一环仍被切断：编译/修复全部在生成页
修复中心（步骤 10），用户在代码栏改完 main.c 或其它 .c/.h 后，想验证必须切回
生成页手动找编译入口；生成页的编译错误跳转（工单 compile-error-jump/01）也只
跳步骤 8 的 main.c 预览卡，非 main.c 错误只能展开源码行片段，落不进代码栏编辑器。
本特性把「保存 → 编译 → 看错误 → 点错误跳行 → 再改」的闭环补进代码栏本身。

## 方案

1. **状态栏「编译」按钮**（.code-statusbar 内、「去生成页编辑 main.c」旁）。
2. **编译前自动保存**：点击编译 → 先保存全部脏标签（逐个 await；非脏/只读跳过；
   保存冲突 → 弹既有冲突模态（覆盖/重载/取消），取消 → 中止编译并提示；覆盖/
   重载 → 继续编译）。编译读的就是用户当前编辑内容，无需再手动 Ctrl+S。
3. **平台自动推断**：POST /api/compile 只带 {output_dir}，platform 改为可省略——
   缺省走 context_manifest._infer_platform（工程文件后缀判平台：.uvprojx → stm32，
   .cproject/.project → mspm0；两者都有 / 都没有 → 400 中文）。与 /api/flash
   同源同判据。
4. **底部错误面板**（编辑器下方、状态栏上方，可折叠）：编译完成后展示状态行
   （成功「编译通过 · N Error / N Warning · 耗时」/ 失败「N 个错误 · 耗时」）
   + 错误列表（每条 = `path:line` + 消息，点击 → 在代码栏打开该文件并跳行定位）、
   + 失败时「去生成页一键编译修复」引导按钮（仅当当前目录 = 生成上下文时显示，
   判据复用 isMainCDiskDir 单源；点击 = 切生成页 + scrollToStep(10)）。失败自动
   展开，成功默认显示成功状态行（面板可收起，有清除按钮）。
5. **错误行跳转**：点击错误行 → editJumpToFile(path, line)（打开/激活 tab +
   editorLineRange 选区 + 行高亮 + flash，全部复用既有机制）。路径若为 UV4
   `..\` 形态被 /api/code/file 拒绝，走兜底链：先尝试原始 path 打开，失败 →
   POST /api/compile/source-line 取 path_resolved → 再打开跳行。
6. **SSE 消费**：复用 parseSSE + /api/compile done 载荷现有字段（parsed_errors /
   summary / duration / timed_out / passed），契约单源 events.py；不触发
   aiAction 横幅（纯编译不调 LLM）。

## 用户故事

1. 作为改完代码的用户，我想要在代码栏直接点「编译」，以便不用切回生成页就能验证。
2. 作为有未保存修改的用户，我想要编译前自动保存，以便编译用的就是我当前编辑的内容。
3. 作为看到编译错误的用户，我想要点错误行直接打开对应文件并定位，以便不用手动找文件/行号。
4. 作为打开任意目录的用户，我想要平台自动识别，以便不用手动选择 stm32/mspm0。
5. 作为编译失败但需要深度修复的用户，我想要面板上一键去生成页「一键编译修复」，以便不迷路。
6. 作为只想看结果的用户，我想要失败自动展开、成功状态可见、面板可收起，以便不被占屏打扰。

## 实现决策

- **后端**：webapp.py `/api/compile` 的 platform 由 `_require_str` 必填改为可选
  （`payload.get("platform")` 空 → `_infer_platform(output_dir)`，来自
  context_manifest 单源——与 /api/flash 同判据）；确认 ContextError 在 errors.py
  已登记（400 中文表项；未登记则登记，isinstance 顺序保持在 400 大元组语义内）。
  请求侧契约变更只影响 docstring 与（若有）契约测试；done 载荷字段不变。
- **保存全部**：ui/codeeditor.js 新增导出 `saveAllDirtyTabs()` →
  `Promise<{ok: boolean, canceled: boolean}>`——遍历 tabs，对脏且非只读的 tab
  逐个保存（复用 saveActiveTab 的写盘/409 路径）；冲突模态改造为可等待：
  showConflictModal 返回 Promise，三动作（覆盖/重载/取消）各自 resolve；
  单文件 Ctrl+S 路径行为不变（仍弹模态、无等待语义变化——saveActiveTab 内部
  同样可改为 await 该 Promise，行为等价）。取消 → 返回 canceled，编译中止。
- **面板 UI**：index.html #tab-code 内插入 `#code-compile-panel`（.code-layout 之后、
  .code-statusbar 之前）+ 状态栏 `#btn-code-compile`；渲染纯件在
  fx/code-compile.js（状态行/错误行 HTML、面板状态机纯函数），胶水在
  ui/code-compile.js（按钮/面板事件、自动保存编排、SSE 消费、跳转）。
- **跳转兜底链**：编译错误路径先试 /api/code/file（memo 直读），失败（400）再
  /api/compile/source-line 归一重试——避免对每条错误都多发一个 source-line 请求。
- **按钮可用性**：无全局快捷键（最小实现）；编译中按钮 disabled +「编译中…」；
  目录未打开 → toast 中文；平台推断失败 / 工具链缺失 → 400 中文 message 进面板
  状态行 + toast。
- **与既有跳转的关系**：生成页步骤 8 的 compile-error-jump/01 保持不动；代码栏
  跳转是新增路径，复用 editJumpToFile / editorLineRange / resolve_source_path。

## 测试决策

- **后端 pytest**：/api/compile 省略 platform → 推断成功（stm32/mspm0 各一例）；
  两个平台配置都在 / 都没有 → 400 中文；显式传 platform 行为不变（回归）。
  _infer_platform 域级算例已存在于 test_context_manifest，路由层补契约测试。
- **前端 node 纯函数**：fx/code-compile.js（状态行/错误行渲染、面板状态机、
  保存决策编排的纯函数部分）挂 tests/js/code-compile.test.mjs；
  codeeditor.test.mjs 扩展 saveAllDirtyTabs 的决策纯逻辑；
  fx-guard 全域登记校验（新 fx 模块须被覆盖）。
- **CDP 冒烟**：.scratch/code-tab-compile/smoke.mjs——打开生成工程 → 点编译 →
  面板出现（成功状态行或错误列表）→ 点错误行 → tab 打开 + 选区断言；
  回归 smoke-02~12 全绿（尤其保存冲突 smoke-04 与代码栏 smoke-02/03）。
- **契约**：events.py compile done 词表不变（platform 只是请求侧可选），
  改动仅 docstring；webapp /api/compile docstring 同步。
- 现有基线：node tests/js 996 + pytest 3044 + smoke-02~12 全绿为回归门槛。

## 范围外

- 代码栏内 AI 修复 / 烧录 / 深化 / 任务推进（保持生成页，面板仅给「去生成页」引导）。
- 完整底部面板（Problems/Output 多区、持久化、多工具集成）。
- 编译快捷键 / 自动编译（保存后自动触发）/ 错误自动修复循环。
- 外部修改轮询（仍为保存时检测 409）。
- 代码栏错误面板的「编译输出原文」查看（本轮只做结构化列表；输出原文在生成页）。

## 补充说明

- 平台推断失败提示语与 /api/flash 同源（「工程里没有工程配置文件…」），用户
  打开任意资料目录点编译时能得到中文解释。
- 教程（guide-refs）「代码栏：IDE 式代码编辑器」小节补「编译」一句（可并入
  smoke 工单或独立文案工单，落地时按批次取舍）。
- CHANGELOG / 提交信息中文；.ps1（若有探针）UTF-8 BOM。
