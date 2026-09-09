# 01 — 代码查看器 Ctrl+滚轮缩放 + 持久化

**要做什么：** 「代码」tab 只读代码视图（含行号 gutter）支持 Ctrl/Cmd+滚轮
缩放字体：上滚放大、下滚缩小，80%–200%、每档 10%（与生成页 main.c 编辑器
同一 codeZoomClamp 语义）；缩放时视图右上角浮出「当前百分比」提示（1.2s
淡出）；值写入 `firstep.codeViewZoom`，刷新/重开恢复。行号与代码同源缩放
永不错位。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**答：** Ctrl/Cmd+滚轮缩放已实现并验证：CDP 冒烟 30/30、前端单测 937/937、
pytest 2989 passed（后端零改动）。双轴评审整改（--code-font-size 收口、
spec 归一、文件名 wheel）均已落地，见下方「评审整改」节。

- [x] `.code-gutter-line` 与 `.code-pre` 字体改经 `--code-font-size`
       （= `calc(13px * var(--code-zoom, 1))`，挂 `.code-view`）；新增
       `.code-zoom-badge`（右上浮层、pointer-events:none、既有 token，
       挂 `.code-pane-main`——不随 `.code-view` 滚动）。
- [x] ui/codeview.js：`applyCodeZoom(pct)` 单一路径（clamp → 写
       `--code-zoom` → 持久化 `firstep.codeViewZoom` → badge 显示 pct% +
       .show → 1.2s 后移除）；`currentCodeZoomPct()` 反算当前档；init 按
       `parseZoomStored` 恢复。
- [x] wheel 监听（`.code-view`，passive:false）：仅 `ctrlKey || metaKey`
       时 `preventDefault()` + 缩放（上滚 +10 / 下滚 -10）；累积器
       |Δ| ≥ 40 才触发一步（高 DPI/触控板多事件兼容）；无 Ctrl 滚动不受影响。
- [x] 纯件复用 fx/code.js `codeZoomClamp` / `parseZoomStored`（80–200 /
       NaN→100），**不新增** fx 导出；code-zoom.test.mjs 既有单测覆盖；
       fx-guard 不登记新名。
- [x] 缩放跟会话不跟文件：`openCodeFile` 重渲染 innerHTML 后容器
       `--code-zoom` inline 保持（不重置）。
- [x] CDP 冒烟扩展：初始 100%、Ctrl+滚轮放大 → 变量 1.1 + gutter/pre
       font-size 同步（相等且 ≠13px）、连缩 15 档 clamp 到 80%（badge 80%）、
       localStorage 同值、reload 恢复；既有冒烟全绿。
- [x] tests/js 全量绿 + pytest 全量绿（后端零改动）。

## 评审整改（双轴，已落地）

- **Standards 轴**：无硬性文档化标准违规（语言规范中文 ✓、fx/ui 分层与单源复用 ✓）。
  - ① Duplicated Code（判断调用）：`.code-gutter-line` 与 `.code-pre` 的
    `font-size: calc(13px * var(--code-zoom, 1))` 字面量两处重复 → 收口为
    `.code-view` 上一条 `--code-font-size` 自定义属性，两处 font-size 均引用
    （已落地，冒烟 + 全量复测绿）。
  - 观察项（不改）：`CODE_VIEW_ZOOM_ACC` 缩写有尾注释救回；localStorage
    键 `firstep.codeViewZoom` 与 `firstep.codeTreeWidth` 同风格（树宽先例）与
    `firstep.mainc.zoom` 混用——无文档标准，不判违规；模块级 let 与文件既有
    模块态模式一致。
  - 附注（超范围，未收口）：13px 与 `generate-mainc.js` `CODE_ZOOM_BASE=13`
    互为跨模块魔法数——mainc 走 JS 写 px 路径，无法与 CSS 变量共享单源。
  - 名称 nit：本工单文件名 `whell` → `wheel` 已改。
- **Spec 轴**：唯一需归一 = badge 锚点与 `.code-view` 默认声明。选「改 spec
  对齐实现」：badge 挂 `.code-pane-main`（`position:relative`）——不随
  `.code-view` 内容滚动、不惧 `openCodeFile` innerHTML 重渲染；默认 1 由
  `var(--code-zoom, 1)` 兜底（init 即写 inline，功能等价）。spec.md 已同步：
  去掉 JS 侧 `CODE_VIEW_ZOOM_BASE=13`（JS 不写 px，13px 由 CSS 单源）、
  补 `CODE_VIEW_ZOOM_ACC=40`、补累积器余量丢弃说明（单次大幅滚轮只走一步，
  刻意保守防高 DPI 单档连跳）。其余实现（范围/步进/键名/1.2s 淡出/单源复用/
  零新导出）与 spec 全对齐；范围蔓延仅良性（aria-hidden、累积器常量化、
  dispatchEvent 返回 false 断言、冒烟收尾回 100%）。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
