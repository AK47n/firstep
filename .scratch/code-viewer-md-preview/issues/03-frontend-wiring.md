# 03 — 前端接线：.md 预览 + 临时源码 + 大纲标题

**要做什么：** 代码查看器消费 01 的渲染纯件与 02 的图片端点：点击 .md 文件默认渲染预览（VSCode 式排版、无行号 gutter、无行高亮）；右侧大纲对 .md 显示标题清单、点击在预览内滚动定位（flash）；跨文件搜索结果命中 .md 时自动切到该文件临时源码视图（带行号）定位命中行；.md 预览内按 Ctrl+F 自动切临时源码视图过滤；临时源码视图提供「返回预览」按钮，重新点击文件树节点也回预览；新增 `.code-md-preview` 排版 CSS（根字号沿用 `var(--code-zoom)` 与滚轮缩放联动）；「大纲仅 .c/.h」空态文案随 .md 支持更新；既有行为（非 .md 文件、搜索面板、Ctrl+F 过滤、跳行 flash、树拖宽、滚轮缩放）零回归。

**被谁阻塞：** 01（Markdown 渲染纯件）、02（后端图片二进制端点）。

**状态：** resolved

- [x] 打开 .md 文件：默认渲染预览（标题/表格/代码块/清单/引用/加粗/本地图片均可视），无行号 gutter；图片相对路径以 .md 所在目录为基准、`../`/绝对/协议路径渲染占位不请求。
- [x] .md 右侧大纲 = 标题清单（徽标 H），点击在预览内滚动定位并 flash；非 .md 文件大纲行为不变。
- [x] 跨文件搜索结果命中 .md：点击后进入该文件临时源码视图并定位命中行；命中非 .md 文件行为不变。
- [x] .md 预览内 Ctrl+F：自动切临时源码视图并聚焦过滤输入，过滤/命中跳行生效。
- [x] 临时源码视图顶栏出现「返回预览」按钮，点击回到预览；重新点击文件树同一文件也回预览。
- [x] 非 .md 文件（c/h/xml/txt）行为逐项不变（行号/点击高亮/大纲/搜索/Ctrl+F）。
- [x] `.code-md-preview` 排版生效且 Ctrl+滚轮缩放对预览字体联动；树宽拖拽/记忆互不干扰。
- [x] 既有测试全绿（pytest + node --test）；CDP 冒烟脚本补 .md 预览/临时源码/返回预览/图片步骤并绿。

## Comments

- 实施：ui/codeview.js 两态接线（openCodeFile(path, mode) / renderMdPreview / renderCodeSource / updateCodeBackPreview / jumpToMdLine / codeImageUrl + normalizeRelPath / 大纲分支 / 搜索命中 mode=source / Ctrl+F 先切源码 / 返回预览 / 失败与 loadCodeDir 复位）；fx/codeview.js 大纲 heading:"H" 徽标 + 空态文案；index.html 顶栏行结构（#code-current-path + #code-back-preview）+ .code-md-preview 排版 CSS（根字号 calc(15px*var(--code-zoom,1)) 与滚轮联动、标题 em 梯度、表格/代码块/引用/任务/hr/img/链接、[data-md-line].flash）；新增 .scratch/code-viewer-md-preview/smoke.mjs（17 项：树/预览排版/图片 /api/code/raw 归一加载/3 坏占位/MD 徽标/大纲 H 1-3-9 滚动 flash/搜索→临时源码/返回预览/Ctrl+F 切源码聚焦/过滤/点树回预览/main.c 零回归/预览缩放联动）。既有 code-viewer/smoke.mjs 30 项回归全绿。
- 双轴评审：Standards——无硬违反；整改 4 项判断项：①scheme 正则三处重复 → fx/markdown.js 抽 hasScheme 单源（isSafeUrl/isSafeImageSrc/胶水 codeImageUrl 共用，含单测）；②jumpToMdLine/jumpToLine flash+1200 重复 → flashEl + CODE_FLASH_MS=1200 常量（缩放浮标同归拢）；③两态复位 loadCodeDir/失败支重复 → resetMdView()；④侧栏「搜索」tab 直输不切源码（预览态点击命中静默落空）→ find input 事件先切源码，且 openCodeFile md 预览分支清掉上一文件遗留过滤值（保「点树回预览」）。Spec——无缺失无蔓延；两点可打磨边角：遗留过滤值（已修）；isSafeImageSrc 拒绝一切 ../ 比 spec「跨出打开根才拒」更保守（安全向刻意收窄，注释言明，保持）。
- 验证：node --test 959 项全绿（含 hasScheme 用例）；.md 冒烟 17/17；既有冒烟 30/30；全量 pytest 3007+ 绿。
