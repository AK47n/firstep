# code-viewer-polish — 代码查看器 UI 打磨（对照 CCS 观感）

## 问题陈述

「代码」tab 打开工程后视觉观感远逊 IDE：对照 Code Composer Studio 截图——
① 文件树无类型图标、层级感弱；② 编辑器区只有裸行号 + 裸代码，无「编辑器」
质感（行号栏无当前行联动）；③ 顶栏只有一行纯文本路径，无 CCS 顶部
`c main.c` 标签观感；④ 跳行仅 flash 1.2s，无持续当前行高亮，长文件定位
难。用户反馈：「相较于 CCS 的代码查看界面，现在我们这个太丑陋了」。

## 方案（用户已确认的选择）

打磨范围 = 文件树 IDE 化 + 编辑器区 IDE 化 + 顶栏文件标签观感 +
当前行高亮；编辑区基调**跟随主题**（深浅自动适配，不做固定深色面板）；
不做 minimap / 多文件 tab / 空态专项（用户未选，范围外）。

### 文件树 IDE 化（工单 01）

- fx/codeview.js 新增 `fileIconHTML(path, isDir)`：内联 stroke SVG（16px、
  `stroke="currentColor"`，风格照 fx/btn-icon.js 单源约定——按钮图标是
  btn 专用，文件树图标本模块自建不 import 耦合）；按扩展名映射图标：
  文件夹 / C 源码（.c）/ 头文件（.h 等）/ 文档（.md .txt）/ 配置
  （.json .syscfg .uvprojx .cproject .xml）/ 汇编（.s .S .asm）/ 产物
  （.o .obj .out .map .hex）/ 其余通用文件；未知扩展名 → 通用文件图标。
- `codeTreeHTML` 树节点前渲染图标 span（目录 = 文件夹图标 + summary；
  文件 = 类型图标）；CSS `.code-tree-icon`（flex none、muted、竖排对齐）。
- 树形连接线沿用既有 `.code-tree .code-tree { border-left }`，微调缩进与
  行高让层级感更贴近 IDE。

### 顶栏文件标签观感（工单 01）

- fx/codeview.js 新增 `codeFileTabHTML(path, lang)`：`code-file-tab` 结构
  = 语言徽标（C / XML / TXT——沿用 fx/highlight.js languageOf 单源）+ 文件
  名 + `data-tab-path`；**纯展示**（当前只有一个文件，不多开 tab）。
- ui/codeview.js：openCodeFile 成功后把 #code-current-path 的纯文本渲染
  换成 tab 渲染（title 仍带完整相对路径，悬停可查）；未打开文件时该行
  保持空态文本。
- CSS：`.code-file-tab`（panel 底色、顶部圆角、底部 2px accent 线、
  悬停态），badge `code-file-tab-badge`（mono 小徽章）。

### 编辑器区 IDE 化 + 当前行（工单 02）

- 当前行（用户选择「要」）：点击代码行（.code-pre-line）→ 移动
  `.active` 类（持续淡色背景）；既有 flash 保留为跳行瞬态强调（1.2s 后
  还原到 active 或无色）。active 与 flash 用同一 accent 色相不同 alpha
  （`:root` 双主题自适应允许 `rgba(var(--accent-rgb), a)` 变体）：
  active = `.07` 淡、flash = 既有 `--accent-dim(.12)` 略强。
- 行号联动：`.code-gutter-line.active` 同索引加粗 + accent 色；jumpToLine
  与点击同时更新 gutter active（gutter 行与内容行同 data 键对齐）。
- 排版：gutter 宽度随最大行号位数（3 位以上加宽）、行号与代码行高已对齐
  不动；代码区 padding / 滚动条沿用既有 token；空文件与长行行为不变。

## 用户故事

1. 打开工程后，文件树每个节点带类型图标（C / 头文件 / 文件夹 / 文档等），
   一眼分辨文件种类。
2. 打开文件后，顶栏显示 `C main.c` 式标签，观感贴近 CCS 编辑器顶部。
3. 点击任意代码行，该行持续淡色高亮 + 行号加粗，当前行定位清晰。
4. 大纲 / 搜索跳行后，当前行高亮跟随移动（flash 瞬态 + active 持续）。
5. 深浅主题下观感均协调（跟随 token，不另造色值）。

## 实现决策

- **前端 fx 纯函数**：`fileIconHTML` / `codeFileTabHTML` 进 fx/codeview.js
  （本模块专属，不进 btn-icon.js——按钮/文件树图标语义不同）；SVG 尺寸与
  stroke 风格照 btn-icon 先例（16px、width 15/16、stroke-width 1.5）。
- **ui 胶水**：当前行点击委托注册在 #code-viewer（内容行元素每次渲染重建，
  用容器的 `closest('.code-pre-line')` delegation，渲染后无需重绑）；
  jumpToLine 增加 active 移动（flash 逻辑保留）。
- **CSS**：全部用既有 token（--panel / --panel-2 / --border /
  --accent / --accent-dim / --muted / rgba(var(--accent-rgb), a)），
  **不新造颜色值**；新类名一律 .code-* 前缀。
- **模式变更**：无——纯前端视觉打磨，后端 / API / 载荷零改动。
- **后端**：零改动。

## 测试决策

- 主 seam = tests/js 纯函数单测（既有 codeview.test.mjs 扩展）：
  fileIconHTML（.c/.h/.md/.json/.syscfg/未知 → 图标类名与 SVG 存在性）、
  codeFileTabHTML（badge 文案 C/XML/TXT、data-tab-path、转义）、
  codeTreeHTML（文件行含图标 span、目录含文件夹图标；既有断言不破）。
- 交互 seam = 既有 CDP 冒烟（.scratch/code-viewer/smoke.mjs）扩展：
  树第一个文件行含 .code-tree-icon；打开 main.c 后顶栏含 .code-file-tab
  与徽标 C；点击第 3 行 → .code-pre-line.active 且在 gutter 同索引
  `.code-gutter-line.active`；大纲跳行后 active 移动到目标行。
- 回归：pytest 全量 + tests/js 全量保持绿（本需求后端零改动，pytest 应
  全数不变）。

## 范围外

- minimap / 右侧缩略图（用户明确不要）。
- 多文件 tab 并行 / 标签关闭（顶栏 tab 为当前文件纯展示）。
- 空态 / 整体配色专项（用户未选；仅随行就位，不单独设计）。
- emoji 图标（全站图标体系为 stroke SVG，保持一致）。
- 后端 / API / 载荷变更；编辑写回（仍只读）。

## 补充说明

- 树图标为 15-16px inline SVG，`aria-hidden="true"`，纯展示不干扰
  data-code-file 点击事件。
- 当前行点击与大纲/搜索跳行共用同一 active 设置路径（避免两套状态漂移）。
- 本打磨不改动 fx/highlight.js（高亮单源不动）、不改行高与字体
  （1.55 / --mono 保持，避免 gutter 与内容行错位）。
- 实现细节：gutter 行号 span 补 `data-code-line`（与 .code-pre-line 同
  data 键——spec 主行号与内容行同键要求，跳行 / 当前行按索引统一寻址）；
  树图标由 fx/codeview.js 自建（CODE_ICO_* 常量，照 btn-icon.js stroke
  风格），不 import 按钮图标模块；CSS 字号守卫拦下过 badge 10.5px 裸值
  （改 11px）。
- 验收观感：.scratch/code-viewer-polish/shot-polished.png（树图标 +
  C main.c 标签 + 当前行高亮 + 行号联动，深色主题）。
