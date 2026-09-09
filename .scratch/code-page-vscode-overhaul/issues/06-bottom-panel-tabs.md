# 06 — 底部面板 tab 化

**要做什么：** 编译 / 磁盘变更 / AI 对话 / 修复 / 烧录五个独立堆叠面板合并为一个底部面板容器 + 页签条，同一时刻只显示一个面板；页签点击切换；有内容的页签显示、无内容（从未触发）隐藏；新消息到达自动切到对应页签并显示；各面板独立 `.collapsed` 收起态保留（收起只收内容，页签与头部常驻）；面板头部状态行、按钮、事件 id 全部保留（少动业务 JS）。

**被谁阻塞：** 无——可立即开始。

**Type:** task
## Answer

已实现并验证：

- 新增 ui/code-bottom-panels.js：单容器 #code-bottom-panels + 页签条
  #code-bottom-tabs（role=tablist）；showPanel(id)（触发标记 + 自动切换）、
  hidePanel(id)（撤页签 + 活动回退）、initCodeBottomPanels()（页签点击切换）；
  容器显隐 = 有无已触发面板；页签只渲染触发过的面板。
- index.html：五面板（编译/磁盘变更/AI 对话/修复/烧录）收进容器；CSS 底座
  移到容器，页签样式变量驱动（双主题）；各面板 DOM/事件 id/收起按钮全保留。
- 接线（业务 JS 只改显隐调用）：code-compile.js（openPanel→showPanel、清空→
  hidePanel）、code-ai-chat.js（openPanel/setCodeAiDir）、code-fix-panel.js、
  code-flash.js（openPanel→showPanel）、codeview.js renderChangePanel（有/无
  条目 → showPanel/hidePanel）；initCodeViewer 调 initCodeBottomPanels。
- 冒烟 smoke-06.mjs 11/11 PASS（初始隐藏零页签、自动切页签、点击切换、同时
  只显示一个、收起态独立保留、hidePanel 回退、全撤隐藏）+ smoke-06a-imports
  6/6（接线模块导入图完整）；深色截图 shot-06-bottom-tabs-dark.png。
- 全量测试通过；不触发真实编译/烧录/AI API（冒烟用模块驱动 + 接线经
  code-review 核对）。

**Status:** resolved

## 实现要点

- 面板 DOM（`#code-compile-panel` / `#code-change-panel` / `#code-ai-chat-panel` / `#code-fix-panel` / `#code-flash-panel`）移入单容器 + 页签条；新增容器模块 `showPanel(id)`，既有各面板「完成事件」改接到它（自动切页签 + 页签出现）。
- 页签带 aria-label/title；无内容页签不渲染；容器的显示/隐藏逻辑保持与现状等价（面板内容事件触发时容器不再整块隐藏）。
- 不改变状态栏与各面板内部业务逻辑。

## 验收 checklist

- [x] 深色主题下：底部单容器 + 页签条；点击页签切换五个面板；同一时刻只显示一个。
- [x] 编译完成 → 自动切「编译」页签；AI 回复 → 切「AI 对话」；磁盘变更 / 修复 / 烧录同理（冒烟至少覆盖编译一条）。
- [x] 每面板收起态独立保留（收起其它页签面板内容、头部状态行仍在）。
- [x] 从未触发的面板页签不显示。
- [x] 既有面板功能（编译输出、AI 对话、烧录、修复、清空按钮）不回归。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
