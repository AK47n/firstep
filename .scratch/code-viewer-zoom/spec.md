# 代码查看器 Ctrl+滚轮缩放（code-viewer-zoom/01）

## 问题陈述

「代码」tab 只读代码视图的字体大小固定 13px：看长文件/小字段时字号偏小，想临时放大；看长函数又想缩小一次看更多行。目前只能靠浏览器页面缩放（Ctrl+滚轮会缩放整个页面，布局全乱），没有代码区独立的快捷缩放。生成页的 main.c 编辑器已有工具栏 +/- 缩放（`firstep.mainc.zoom` 先例），代码查看器没有。

## 方案

在「代码」tab 的只读代码视图（`.code-view`，含行号 gutter 与代码高亮层）上支持 **Ctrl（Mac 为 Cmd）+ 鼠标滚轮** 滚轮缩放：上滚放大、下滚缩小，每档 10%，范围 80%–200%（与 main.c 编辑器一致的 `codeZoomClamp` 语义）。缩放过滚轮时在视图右上角浮出「当前百分比」小提示（1.2s 后淡出）。缩放值写入 `localStorage`（键 `firstep.codeViewZoom`），刷新/重开后恢复。

实现要点（照 main.c 三明治先例的「单层字体基准」思路，但用 CSS 变量单点）：

- `.code-gutter-line` 与 `.code-pre` 的 `font-size: 13px` 改为引用 `.code-view`
  上单条自定义属性 `--code-font-size: calc(13px * var(--code-zoom, 1))`
  （两处使用同一来源，13px 基础只写一次）——gutter 与代码同源缩放，行高
  （unitless `line-height: 1.55`）、空行 `min-height: 1.55em`、gutter
  `min-width: 3ch` 全部 em/倍数联动自动同步，行号与代码永不错位。
- JS 只写一个变量：`#code-viewer` 容器 `style.setProperty("--code-zoom", pct/100)`；`openCodeFile` 的 `innerHTML` 重渲染不影响容器自身 inline style（缩放跟会话不跟文件）。
- 纯件复用：`codeZoomClamp`（80–200，NaN→100，四舍五入）与 `parseZoomStored`（null→100，parseInt 容错）已在 `fx/code.js` 并已有单测，直接 import，不新增重复实现（单源）。
- 滚轮回调：监听 `.code-view`（滚动容器本身），`wheel` 事件 `{passive:false}`；仅 `ctrlKey || metaKey` 时 `preventDefault()`（阻止浏览器页面缩放）并缩放；其余情况交还原生滚动。滚动增量用累积器（`|Δ| ≥ 40` 才触发一步，兼容高 DPI 鼠标/触控板多事件）。
- 百分比指示：`.code-zoom-badge` 绝对定位右上（pointer-events:none，`--panel`/`--border`/`--radius-sm` 既有 token，缩放时 `textContent = pct + "%"` + `.show`，1.2s 后移除）。

## 用户故事

1. 作为查看代码的用户，我想在只读代码视图上按 Ctrl+滚轮直接缩放字体，以便不用浏览器整页缩放就能看清/看全代码。
2. 作为用户，我希望行号 gutter 与代码同步缩放，以便缩放后行号仍与代码行对齐、跳行高亮不漂移。
3. 作为用户，我希望缩放范围有限（80%–200%，每档 10%），以便不会缩到不可读或撑破布局，且与生成页 main.c 编辑器行为一致。
4. 作为用户，我希望缩放时能看到当前百分比提示（浮出后自动淡出），以便知道当前字号档位。
5. 作为用户，我希望缩放值被记住（刷新/下次打开恢复），以便不用每次重调。
6. 作为用户，我希望 Ctrl+滚轮只影响代码视图本身（浏览器页面缩放被阻止），以便页面其它布局不被缩放。
7. 作为用户，我希望鼠标不带 Ctrl 的普通滚轮仍正常滚动代码，以便浏览长文件不受影响。

## 实现决策

- 构建/修改的模块：
  - `src/contest_generator/static/index.html`（CSS：`.code-gutter-line` 与 `.code-pre` 字体改引用 `.code-view` 上单条 `--code-font-size: calc(13px * var(--code-zoom, 1))`（默认 1 由 var 兜底，无需容器显式声明）；`.code-pane-main` 增加 `position: relative`（badge 锚定——不随 `.code-view` 内容滚动、也不惧 innerHTML 重渲染）；新增 `.code-zoom-badge` 样式；无 HTML 结构变化——badge 由 JS 动态挂到 `.code-pane-main` 内）。
  - `src/contest_generator/static/js/ui/codeview.js`（胶水：常量 `CODE_VIEW_ZOOM_KEY="firstep.codeViewZoom"` / `CODE_VIEW_ZOOM_STEP=10` / `CODE_VIEW_ZOOM_ACC=40`；`currentCodeZoomPct()` 读 `--code-zoom` 反算、`applyCodeZoom(pct)` 单一路径 clamp→写变量→持久化→badge；`initCodeViewer` 内初始化：恢复存储值 + wheel 监听（累积器）+ badge DOM 创建）。
  - `src/contest_generator/static/js/fx/code.js`：**零改动**（复用 codeZoomClamp/parseZoomStored）。
  - `.scratch/code-viewer/smoke.mjs`：扩展 Ctrl+滚轮冒烟。
  - `.scratch/code-viewer-zoom/`：本 spec 与工单。
- 接口：不新增 fx 导出（复用既有单源）；不新增后端端点；不新增 HTML 结构（badge JS 动态创建——避免 index.html 死元素，badge 无文本默认不占位）。
- 技术澄清：
  - `--code-zoom` 为数值（1 = 100%），`calc(13px * var(--code-zoom, 1))` 直接相乘；JS `setProperty("--code-zoom", String(pct/100))`。**JS 不持有 13px 基数**（无 px 写入路径），故无 `CODE_VIEW_ZOOM_BASE` 常量——13px 由 CSS calc 单源。
  - wheel 方向：`deltaY < 0`（上滚）放大 `+10`，`deltaY > 0`（下滚）缩小 `-10`。
  - badge 复用 jump 的 1.2s 淡出节奏；重复缩放时重置计时器。
  - 初始化时若存储值非法/缺失 → 100%（`parseZoomStored`）。
  - 缩放仅作用于 `.code-view` 内文本；树、侧栏、大纲不受影响。
  - 累积器每步触发后清零（超出 40 的余量丢弃）：单次大幅滚轮只走一步 10%，多档需连续滚动——刻意的保守行为（避免高 DPI 单档多事件连跳）。
- 架构决策：**不加新纯函数**——clamp/parse 全域已有单源（fx/code.js，code-zoom/01 工单），本工单只写胶水 + CSS 变量，避免第三套缩放实现。
- API 契约：无后端涉及。
- 具体交互：Ctrl+滚轮（含 Cmd）；范围 [80,200]；步进 10；持久化键 `firstep.codeViewZoom`；badge 文本如 `120%`。

## 测试决策

- 什么构成好测试：外部行为（滚轮 → 字号变化 + 持久化 + 指示），不测内部实现。
- 将测试哪些模块：
  - `tests/js/code-zoom.test.mjs`：既有 codeZoomClamp/parseZoomStored 单测**无需改动**（复用即单源）；不新增 fx 名称 → fx-guard 不登记。
  - `.scratch/code-viewer/smoke.mjs`（CDP）：新增块——①清 `firstep.codeViewZoom` 后 reload，初始 CSS 变量 1（100%）；②合成 `WheelEvent`（`ctrlKey:true, deltaY:-100`）→ `--code-zoom` 变 1.1（110%）且 gutter/pre `font-size` 同步（二者相等且 ≠13px）；③凑足下限/上限（连续缩小 15 档 → clamp 80%，badge 显示 80%）；④localStorage 值 = clamp 后 pct；⑤再次 reload → 恢复该值（确定性：本轮以 100% 收尾）。
  - 既有冒烟（树/文件/大纲/搜索/Ctrl+F）全部保持绿。
- 测试既例：code-zoom.test.mjs（纯函数先例）、smoke.mjs（DOM 可观察断言先例）。

## 范围外

- 不加工具栏 +/- 按钮（main.c 已有；本次只滚轮）。
- 不加 Ctrl+= / Ctrl+- / Ctrl+0 键盘缩放（用户未要求；后续可按需增量）。
- 不改生成页 main.c 编辑器（保持其现有实现；如需滚轮另行工单）。
- 不做双击复位/重置按钮。
- 不做最小地图（minimap）相关。

## 补充说明

- 与既有 `firstep.codeTreeWidth`（树宽持久化）同属「代码查看器设置」族，键名风格一致（`firstep.codeViewZoom`）。
- Mac 触控板捏合 = ctrl+滚轮（浏览器层），同样被本监听接管（`metaKey` 一并判定）；普通两指滚动不打 Ctrl，不受影响。
