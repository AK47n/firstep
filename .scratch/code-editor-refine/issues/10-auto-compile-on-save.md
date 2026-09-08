# 10 — 保存自动编译开关

**要做什么：** 新增「保存后自动编译」开关（默认关）：开启后，用户手工保存成功（Ctrl+S/保存按钮，非程序化自动保存）→ 触发编译（复用 runCodeCompile：内部自动保存全部 + SSE + 错误面板）；编译中不重复触发；开关 localStorage 持久化；UI 位置：设置页「编辑」组（若无合适分组则放代码栏状态栏「自动编译」toggle，实现时择一处）。零后端改动。

**被谁阻塞：** 无。

**Type:** task
**Status:** resolved

## 实现要点

- 设置模块加布尔项（键名如 codeEditor.autoCompileOnSave，默认 false）；保存成功回调处挂触发钩子（仅当开关开 + 非编译中 + 本次为手工保存）。
- 手动点「编译」不受开关影响；编译失败只进错误面板（不弹额外提示）。

## 实现决策备注（双轴评审后回写，workflow.md step 4）

- **UI 择一处**：设置页无「编辑」组（settings.js 现为 API/记录/折叠分组），按工单授权放**代码栏状态栏 toggle**（`#btn-code-auto-compile`，.on = accent-dim token，深浅主题自适应）。
- **manual 判据线程化（Standards/Spec 重点整改）**：onFileSaved 回调第三参 manual——手工 = Ctrl+S/保存按钮/「保存全部」（saveAllFromBar 传 true）/冲突「覆盖写盘」（saveActiveTab 与 saveTabSettled 两处均传 true）；程序化 = 编译前 saveAllDirtyTabs 自动落盘/写盘守卫/烧录前置落盘/磁盘重载通知（缺省 false）。`saveAllDirtyTabs(manual?)` 参数化（既有调用零参数 = false 不变）。
- **键名**：`firstep.autoCompileOnSave`（评审整改：沿既有 firstep.* 命名域；fx/code-compile.js AUTO_COMPILE_KEY 单源导出 + window 桥）。
- **存储写失败**：隐私模式禁用存储 → toast「未生效」+ 按钮回读真实态（不假报成功）。
- **编译失败提示**：复用 runCodeCompile 既有 catch（toastError + 面板 err）——与手动编译同路径，工单「不弹额外提示」按「无新增提示」理解（注释明示）。
- **编译中连续保存**：auto 钩子查 compileBusy（与 runCodeCompile 自身防重入双保险）。
- **冒烟覆盖**：默认关/开触发/编译中不重复（pending 桩）/刷新持久化/再点关闭 5 场景，9 项断言。

## 验收 checklist

- [x] 默认关：保存不触发编译；开启后保存触发编译（CDP 断言 /api/compile 调用 1 次 + 面板「编译成功」）。
- [x] 编译中连续保存不重复触发（pending 桩下第 2 次保存仍 2 次调用）；开关刷新后持久化（localStorage + 按钮文案）。
- [x] 开关 UI 可见可点（代码栏状态栏一处）；深色主题样式一致（.on 用 --accent/--accent-dim token）。
- [x] CDP 冒烟 smoke-10 9/9（开 → 保存 → 编译触发；关 → 保存 → 不触发；日志存证）。全量单测 pass；smoke-08 回归 10/10。
