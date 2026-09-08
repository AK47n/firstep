# 08 — 滚动窗口化渲染

**要做什么：** 打开大文件（上千行）时滚动流畅：高亮层 / 行号 gutter / 标记层 / 引导线只渲染可视行 + 上下 overscan，上下各一个 spacer 撑起总滚动高度；textarea 保持全量内容（透明覆盖层，编辑语义不变）；折叠视图行与可见行做映射（折叠后总行数变化仍正确）。

**被谁阻塞：** 07（引导线层渲染要一并窗口化，避免重复返工）。

**Type:** task
## Answer

已实现并验证：

- 滚动窗口化：fx `codeWindowRange(scrollTop, viewportH, lineH, lineCount,
  overscan)`（含层顶 padding 8px、overscan、钳制、至少 1 行）；hl/marks/gutter
  三层只渲染视口窗口行（上下 WIN_OVERSCAN=20），上下 spacer 撑起全高——
  窗口内滚动零 DOM（winRender 同窗直接返回），跨窗口 rAF 节流重建；textarea
  全量（选区/光标/横滚度量基础）；.code-edit 显式尺寸（行高*行数+16px；
  宽度 = 最长行探针实测 + 36px，CJK 双宽也精确）。
- 逐行缓存：内容变化时 highlightCodeLines 整段一次（跨行 token 行界闭合/
  重开、行间独立），数组切片复用；codeFoldGutterLines / codeGutterLineHTML
  单源拆分（codeFoldGutterHTML / codeLineNumbersHTML 重构为拼接）。
- setActiveLine / editJumpToLine 改 data-code-line 寻址 + 跳行先滚动到目标
  再同步渲染窗口（flash 不被重建冲掉）；codeWindowRefresh() 供缩放后重测；
  scroll 监听 + ResizeObserver。
- 前置阻塞修复：服务器 clex.match_bracket 旧实现 O(n²)（5000 函数 84s，打开
  即卡）→ 早停扫描 O(闭合跨度)，/api/code/file 5000 行 .c > 60s 超时 → 446ms
  （独立提交 53e66d00，tests/test_clex.py +3：预处理行跳读、早停不越界、
  5000 函数 <8s 性能回归线）。
- 单测 tests/js/code-window.test.mjs 8 例全绿；CDP 冒烟 smoke-08.mjs 10/10
  PASS（5000 行 DOM 仅 39-60 节点、中部窗口 [2481,2540] 行号正确、窗口内
  零 DOM、输入/回顶正确）；回归 03/04/07 冒烟全过；全量 Python 3159 + JS
  1205 通过。

**Status:** resolved

## 实现要点

- fx 纯件：`windowOf(scrollTop, viewportHeight, lineHeight, totalLines, foldMap?, overscan)` → `{startLine, endLine, topSpacerPx, bottomSpacerPx}`，可单测（含折叠 viewModel 映射、overscan、边界）。
- ui 层：`.code-hl` / `.code-gutter` / 标记层按窗口重绘；滚动事件节流（rAF）；折叠/查找/选中词/括号不回归。
- 行为差异记录：用既有样例工程 + 5000 行合成 .c 文件实测滚动帧率（肉眼 + Performance 面板粗测，不做自动化断言）。

## 验收 checklist

- [ ] 纯件测试：窗口计算、spacer 高度、overscan、折叠行映射、边界（空文件/满屏/末尾）。
- [ ] 深色主题下打开大文件滚动流畅（肉眼无卡顿），行号/高亮不漂移、无跳变。
- [ ] 折叠/展开、查找、选中词、括号配对在窗口化后仍正确。
- [ ] 打开/滚动后选区与光标不串位；既有测试全绿。
