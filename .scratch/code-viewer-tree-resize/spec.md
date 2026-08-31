# code-viewer-tree-resize — 代码查看器文件树面板可拖拽调宽

## 问题陈述

「代码」tab 文件树面板固定 240px 宽。工程嵌套层数多时，每深一层缩进
8px（`.code-tree .code-tree { padding-left: 8px }`），深层文件夹/文件名
被 `text-overflow: ellipsis` 截断——用户反馈「文件树如果层次多那么后面的
文件夹名字看不全」。默认宽度无法调整，深层路径始终看不全。

## 方案（用户已确认的选择）

文件树面板右缘加**拖拽手柄**，拖动即调宽（下限 160px、上限 720px 且
不超过布局宽 - 480px 保留主区/侧栏可用）；宽度写入 localStorage
（`firstep.codeTreeWidth`），刷新/重开后恢复；**双击手柄复位默认 240px**。
布局改由 CSS 变量 `--code-tree-w` 驱动（`grid-template-columns:
var(--code-tree-w) minmax(0,1fr) 300px`），纯前端、后端零改动。

### 拖拽交互细节

- 手柄 = `.code-pane-tree` 右缘绝对定位竖条（8px 命中区，`cursor:
  col-resize`，`position: relative` 挂在树面板）；Pointer Events 实现
  （pointerdown → setPointerCapture → pointermove 算宽 → pointerup 落盘）。
- 拖拽期间 body 加 `.code-resizing`：禁用文本选中（user-select: none）、
  光标统一 col-resize，防拖拽误选树文本。
- 宽度计算：`e.clientX - layout.getBoundingClientRect().left`（树面板左缘
  = layout 左缘），取整后经 `treeWidthClamp(px, layoutW)` 收敛，写回
  `--code-tree-w`。
- 键盘可达（a11y）：手柄 `tabindex="0"` + `role="separator"` +
  `aria-orientation="vertical"`，ArrowLeft/ArrowRight 按 16px 步进调整，
  Home/End 复位默认/上限（与拖拽同一应用路径）。
- localStorage 写入统一 try/catch（照 `firstep.mainc.zoom` 先例），
  读取经纯函数 `parseTreeWidthStored(raw, layoutW)` 解析 + 收敛。

## 用户故事

1. 作为查看器用户，我能拖动文件树右缘加宽/收窄面板，深层文件夹名
   不再被截断。
2. 作为查看器用户，我调整过的树宽在刷新/重新打开目录后保持，不用
   每次重拖。
3. 作为查看器用户，双击拖拽手柄即可回默认宽度（240px）。
4. 作为键盘用户，我可以聚焦手柄用方向键微调宽度（16px 步进）。
5. 深/浅主题下手柄观感协调（沿用 --border/--panel-2 token，不新造色值）。

## 实现决策

- **fx 纯函数**（进 fx/codeview.js，模块专属不 import 耦合）：
  `treeWidthClamp(px, layoutW)`（min 160 / max min(720, layoutW-480)；
  非数值/非有限 → 默认 240；layoutW 非法时按 720 上限）、
  `parseTreeWidthStored(raw, layoutW)`（null/空/非法 → 240，
  解析后走 clamp）。常量 `CODE_TREE_WIDTH_MIN=160`、
  `CODE_TREE_WIDTH_MAX=720`、`CODE_TREE_WIDTH_DEFAULT=240` 同模块导出。
- **ui 胶水**（ui/codeview.js initCodeViewer 内）：在手柄上绑定
  pointer 事件 + 键盘事件；`applyTreeWidth(px, persist)` 单一路径
  （写 CSS 变量 + 可选落盘）；init 时读取存储并应用一次（layout 宽在
  DOM 就绪后取，`layout.clientWidth`）。
- **CSS**（index.html）：`.code-layout` 改
  `grid-template-columns: var(--code-tree-w, 240px) minmax(0,1fr) 300px`；
  `.code-pane-tree { position: relative; min-width: 0 }`；
  新增 `.code-tree-resize-handle`（绝对右缘竖条、hover/拖动高亮、
  聚焦 outline 用 --accent 既有 token）；`.code-resizing` body 级别
  user-select 关停。全部沿用既有 token，不新造颜色值；
  新类名 `.code-*` 前缀。
- **后端 / API / 载荷**：零改动。
- **默认值**：240（与现行为一致，未存过存储时不变）。

## 测试决策

- 主 seam = tests/js/codeview.test.mjs 扩展纯函数用例：
  treeWidthClamp（160 下限 / 720 上限 / layoutW 收窄上限 / NaN 与
  非数值 → 240 / 小数取整）、parseTreeWidthStored（null/空/非法 →
  240、"350" → 350、"9999" → 按 layoutW 收敛）。
- fx-guard.test.mjs：fx/codeview.js 域名登记新增 4 个导出名
  （函数 + 3 个常量——常量登记 typeof "number"）。
- 交互验证 = 既有 CDP 冒烟（.scratch/code-viewer/smoke.mjs）扩展：
  手柄存在；`--code-tree-w` 初始 240px；模拟 pointer 拖动后
  `--code-tree-w` 变化且 localStorage 写入；双击复位 240。
- 回归：tests/js 全量 + pytest 全量保持绿（后端零改动）。

## 范围外

- 右侧栏（大纲/搜索）拖拽调宽（本次只做文件树面板；侧栏布局若需要另开）。
- 树节点悬停 title 提示（用户本次只选拖拽调宽；完整路径提示另行评估）。
- 拖宽后深层名字仍可能截断（面板已可调宽到 720px 上限，远超需求）。
- 迷你地图 / 多文件 tab / 编辑写回（既有范围外不变）。
- 布局宽度持久化的服务端存储（仅前端 localStorage，跨机器不迁移）。

## 补充说明

- 拖拽算法注意：`.code-pane-tree` 内有 8px padding，按 layout 左缘 +
  clientX 计算新宽（手柄紧贴面板右缘，视觉宽度 ≈ 赋予宽度）。
- 与 `.code-tree-box { overflow: auto }` 兼容：面板变宽后树内容自然
  更可见；横向滚动行为不变。
- 存储键 `firstep.codeTreeWidth` 遵循 `firstep.` 前缀约定（先例
  `firstep.theme` / `firstep.mainc.zoom`）。
- fx/codeview.js 已有 `typeof window !== "undefined"` 的 window 导出块，
  新增函数/常量一并登记（fx-guard 只校验模块导出与 index.html 无双源，
  window 登记照既有约定同步）。
