# 01 — 文件树面板拖拽调宽 + 持久化

**要做什么：** 「代码」tab 文件树面板右缘出现可拖拽竖条，拖动即可在
160–720px（且不超过布局宽-480px）范围调宽；宽度写入 localStorage
（`firstep.codeTreeWidth`），刷新/重开后恢复；双击手柄复位默认 240px；
键盘可聚焦手柄用方向键微调（16px 步进）。树深层文件夹/文件名由此可以
看全。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 手柄元素出现在树面板右缘（8px 命中区、cursor col-resize、深/浅
      主题用既有 token、聚焦有 outline），代码查看器「代码」tab 内可见。
- [x] 拖动调宽：pointerdown/move/up 拖拽中 body.code-resizing 禁用文本
      选中；`--code-tree-w` 同步更新，`.code-layout` 网格列宽随之变化；
      范围收敛 [160, min(720, layoutW-480)]。
- [x] 持久化：pointerup 时写 `firstep.codeTreeWidth`（try/catch）；
      init 时按存储值恢复（`parseTreeWidthStored(raw, layoutW)`），
      非法/缺失 → 240。
- [x] 双击手柄 → 复位 240px 并持久化。
- [x] 键盘：手柄 tabindex=0 + role=separator + aria-orientation=vertical；
      ArrowLeft/Right 16px 步进、Home/End 默认/上限，与拖拽同一应用路径。
- [x] fx/codeview.js 新增 treeWidthClamp / parseTreeWidthStored 及
      CODE_TREE_WIDTH_MIN/MAX/DEFAULT 常量；window 导出块登记；
      tests/js/codeview.test.mjs 覆盖 clamp/parse 用例；
      fx-guard.test.mjs 登记导出名。
- [x] CDP 冒烟扩展：手柄存在、初始 240px、拖动后 CSS 变量变化 +
      localStorage 写入、双击复位；既有冒烟全绿。
- [x] tests/js 全量绿 + pytest 全量绿（后端零改动）。

## 评审整改（双轴 code-review 落地，2026-08）

- **规格轴主缺陷（前提不成立，作防御落地）**：评审认为 init 恢复在
  `#tab-code` 隐藏（`section.page{display:none}`）时取宽 0 → 存储值被塌到
  160。实测 `#tab-code` 的 ID 规则 `display:flex`（index.html:1317）特异性
  高于 `section.page`，该 section 从来不是 display:none（初始在 main 之下
  渲染），init 取宽为真实布局宽，恢复正确。仍采纳其防御建议：
  `treeWidthClamp` 对 layoutW 非有限或 ≤0 时 cap=MAX（不塌下限），并补
  用例 treeWidthClamp(350,0)===350 / parseTreeWidthStored("350",0)===350。
- **标准轴判断调用**：抽取 `currentTreeWidth(layout)` 去重 endDrag/keydown
  读取；键盘步进 16 提为常量 `CODE_TREE_WIDTH_STEP`；setPointerCapture
  包 try/catch（合成 PointerEvent 无活动指针会抛 NotFoundError，冒烟用
  合成事件驱动）。
- **范围蔓延确认（良性）**：手柄额外 aria-label/title；`:before` accent 线
  走既有 --accent；fx-guard 建成全 codeview.js 域名（含既有导出，单源强化）；
  冒烟新增清存储键 + 收尾复位（确定性）。
