# 01 — 底部状态栏 VS Code 化

**要做什么：** 代码页底部状态栏从「只有目录路径 + 按钮」升级为 VSCode 式信息状态栏：实时显示光标行列、语言、编码、缩进、缩放，操作按钮样式统一，窄视口信息可折叠。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

**实现笔记：**

- 交付内容：状态栏信息区（#code-statusbar-info）= Ln/Col（accent 色）+ 语言徽标（复用 codeTabBadge）+ 编码（UTF-8 / 非 UTF-8（只读））+ 缩进（空格: 4）+ 缩放 %；随活动标签（onActiveTabChanged）、光标/选区（新增 onCursorChanged 监听，codeeditor 在 select/keyup/input/跳行处 notifyCursor）、缩放（applyCodeZoom）实时刷新；无活动文件显示「未打开文件」占位；窄视口 <900px 隐藏 lang/enc/indent。
- 纯件：fx/codeeditor.js `codeStatusHTML(info)`（无 lang → 空串，边界钳制 Ln/Col ≥1、zoom 0 → 100）；评审整改抽 `caretColOf`（列号 fx 单源，ui 不再手写 lastIndexOf 算式）。
- 评审处置：Spec 轴 3 项（空态占位/边界单测/当前值 accent）已全部落实；「CDP 冒烟缺失」不成立（smoke-01.mjs 已交付且 5 项 ALL PASS）。Standards 轴 0 硬违反；3 判断项中仅 caretColOf 抽取整改，indent:4 字面与 Feature Envy 边界留待后续。
- 测试：tests/js codeStatusHTML（完整/非 UTF-8/xml/空态/边界钳制）+ caretColOf 6 断言；node --test 全量 1101 通过；CDP 冒烟 smoke-01.mjs 5/5。

- [ ] 状态栏左侧保留目录路径（过长省略号收缩），右侧依次显示：`Ln X, Col Y`、语言徽标（C / XML / MD / TXT）、编码（UTF-8 / 非 UTF-8 标「非 UTF-8（只读）」）、缩进（空格: 4）、缩放百分比
- [ ] Ln/Col 随光标移动（键盘 / 鼠标 / 跳行）实时刷新；无打开文件时显示占位（如「未打开文件」）
- [ ] 缩放百分比随 Ctrl+滚轮缩放实时更新
- [ ] 四个现有按钮（保存全部 / 编译 / 烧录 / 去生成页）保留、样式统一为状态栏条钮（不换行、flex:none 不挤压）
- [ ] 窄视口（< 900px）信息段折叠为仅 Ln/Col + 缩放，不挤占按钮
- [ ] 深浅主题下观感协调（只用既有 token，不新造色值）
- [ ] tests/js 新增状态栏格式化纯件单测（0 行 / 只读 / 越界光标 / 中文路径等边界）
- [ ] CDP 冒烟：打开文件 → 状态栏出现 Ln:Col；移动光标 → 数值变化

**补充：** 纯件（格式化文案）与胶水（事件刷新）分层；信息刷新的时机复用编辑器已有 select/keyup/跳行路径，不新造事件。
