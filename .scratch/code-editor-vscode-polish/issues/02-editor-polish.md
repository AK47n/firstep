# 02 — 编辑器视觉精修

**要做什么：** 编辑器本体（代码区 + 行号列 + 空态 + 只读标注）观感向 VSCode 靠拢：细滚动条、选区 / 当前行 / 空态 / 只读标注精修，深浅主题协调。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

**实现笔记：**

- 交付：`.code-empty` 空态（未打开/加载中/加载失败三种分支全部居中，柔性 gap 避 margin 裸值守卫）；`.code-pre/.code-hl/.code-ta` 右 padding 12→24px（横滚尽头留白，三处同步保 1:1 对齐）；`.code-ta::selection` alpha .28→.32；`.code-ro-note` radius-sm + padding 4px 10px（与信息条按钮观感统一）；gutter 行号右 padding 8→12px（与代码左 padding 对齐）。
- 评审处置：Spec 轴 3 缺口（加载失败空态、初始静态占位、gutter 对齐）全部落实；「文件尾空行观感」与「焦点态」判定为既有行为已达标/无需改动（VSCode 同款空行行盒；编辑器焦点即容器焦点，无独立焦点环）。Standards 轴整改：caretColOf 内部钳行尾（ui 层不再手写 lastIndexOf/indexOf）、syncEditorAfterInput 去掉冗余 notifyCursor（每击键只刷一次状态栏）、padding 改动补工单号注释、注释与「未打开文件」占位实现对齐。
- 测试：node --test 全量 1101 通过（含 css-tokens 间距魔法值守卫）；smoke-02.mjs 8/8（空态居中、三明治键位回归、右留白 24px、当前行高亮、只读标注、深浅验收图 shot-editor-dark.png / shot-editor-light.png）。

- [ ] 滚动条细条化（8–10px、thumb 圆角、hover 加深、暗色下可见），横向 / 纵向一致，WebKit + Firefox（scrollbar-width/scrollbar-color）双覆盖
- [ ] 当前行高亮保持淡底 + 左侧竖线，行号 accent 加粗；选区背景增强（高亮色 alpha 提升，深浅主题可辨）
- [ ] 空态（未打开文件 / 加载中 / 加载失败）文案排版精致：居中 muted、与编辑器留白协调
- [ ] 只读标注（非 UTF-8 提示）与信息条按钮观感统一（radius / 字体 / 边框 token 一致）
- [ ] 代码区 padding / 行号列间距微调统一（gutter 右 padding 与代码左 padding 视觉对齐）；文件尾空行观感修正
- [ ] 深浅主题各截一张验收图（.scratch/code-editor-vscode-polish/shot-editor-light.png / shot-editor-dark.png）
- [ ] 既有 DOM 键（.code-hl-line / .code-gutter-line / data-code-line / .code-ta）不删不改，防止破坏既有 CDP 冒烟与跳行/当前行逻辑

**补充：** 纯 CSS + 极少量 HTML 结构微调（如滚动条实现、空态容器）；改动集中在代码页内，不动生成页编辑器。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
