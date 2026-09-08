# 05 — 编译错误行内标记

**要做什么：** 最近一次编译结果的解析错误（path + line + message）由编译模块以内存态持有；打开对应文件时编辑器显示行内标记：行号 gutter 色点 + 错误行下划线/底色 + 悬停 title 显示错误消息；点击错误行/标记跳转（复用既有 jumpToCompileError 定位语义）；重新编译成功清除；不新增后端。

**被谁阻塞：** 无。

**Type:** task
**Status:** resolved

## 实现要点

- 编译模块（code-compile.js）暴露 `getCompileErrors()` / `setCompileErrors(errors)`：done 载荷 parsed_errors 归口（按 path 分组）；编辑器的标记层/行号层读取查询。
- 标记层新 kind：error，扩展既有 MARK_PRIORITY 优先级表（错误 > 括号配对 > 选中词 > 查找命中）；gutter 色点走行号层。
- path 匹配失败时复用既有 source-line 归一（目录前缀/文件预检）逻辑；悬停提示用 title 属性（低成本）。

## 实现决策备注（双轴评审后回写，workflow.md step 4）

- **状态所属（对工单 :12 的文字偏离，方向合理已保留）**：parsed_errors 显示态放在 `ui/codeeditor.js`（`setCompileErrors` 由 code-compile 调用、`getCompileErrors` 成对导出），而非 code-compile 模块内——仓库硬约束「ui 模块间禁止循环依赖」（`ui-cycle.test.mjs` 工具化守卫）：code-compile 已单向 import codeeditor，反向成环立即红；写（renderDone/runCodeCompile/clear）读（标记层/行号色点）语义与工单完全等价。「按 path 分组」改为读时经 fx 纯件 `compileErrorLinesForFile` 懒映射（分组并入行映射）。
- **跳转面（对验收 L19 的合理裁剪）**：行内 `.code-mark-error` 位于透明标记层（`pointer-events:none`、被 textarea 覆盖），点击行内标记会与光标编辑语义冲突——跳转面 = gutter 色点点击 + 编译面板错误行点击（两处都走同一 `jumpToCompileError` 兜底链）。
- **清除时机（对工单只要求「成功清除」的有意扩展）**：编译开始 / 失败 / 清空按钮即清旧标记——重编过程中旧错误残留会误导；代价 = 脏保存被取消时旧标记也清（「未重编时错误仍在」仅在无新编译动作时成立）。
- **显示层归一（对工单 :14「复用 source-line」的部分）**：显示映射用轻量 `compileErrorPathNorm/Base`（无网络往返，可每条错误低开销）；source-line 归一只在点击跳转链复用（jumpToCompileError 预检 + 归一）。`compileErrorPathNorm/Base` 已单源化并供生成页修复中心 `fixKeyOf/fixKeyBasename` 共用（跨簇同域归一不再各写一份）。
- **优先级中段（记录项）**：工单「错误 > 括号配对 > 选中词 > 查找命中」——error=4 置顶达成；中段既有顺序 current(3) > hit(2) > word=bracket(1) 为 04 前遗产，未改动。
- **空行错误行（记录项）**：全行标记靠 span 切割（需 b>a），空行无下划线/底色/title——行号色点 + gutter title 兜底该边缘。
- **越界行号**：currentMarks 按文件行数钳制（跳过）。

## 验收 checklist

- [x] 触发带错误编译 → 打开对应文件 → 行号色点 + 错误行下划线/底色 + title 悬停消息。
- [x] 点击错误标记/行跳转到该行；跳转与既有编译面板点击一致。（跳转面 = gutter 色点 + 面板行，见备注）
- [x] 重新编译成功后标记清除；未重编时切走再切回错误仍在；无错误文件不显示。
- [x] node 单测错误→行映射纯件（compileErrorLinesForFile 4 组 + path 归一 1 组；全量 1224 pass）；CDP 冒烟 smoke-05 11/11（`smoke-05.log` 存证；含深浅主题下色点/标记视觉由 smoke-04 回归 + smoke-05 下划线样式断言覆盖）。
