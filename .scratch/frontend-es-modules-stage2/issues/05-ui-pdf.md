# 05 — PDF tab：static/js/ui/pdf.js + truncate 入 fx 补测

**要做什么：** PDF 资料库 tab 全部 DOM 胶水迁入 `static/js/ui/pdf.js`（列表渲染/统计/过滤器/详情弹窗/trash 弹窗/翻页加载/路径复制/工具栏 init）；顺带把**未测纯函数 truncate** 迁入 fx/core.js 并补 1-2 条轻量单测（用户已批：未测纯函数迁 fx + 补测）。

**被谁阻塞：** 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 区段 = 6648-6935；func：pdfFileUrl 6648 / pdfHealthPredicates 6657 / loadPdfPages 6668 / copyPdfPath 6681 / showPdfDetail 6687 / openPdfTrashConfirm 6742 / pdfTrashDate 6770 / confirmTrashPdf 6778 / confirmTrashGroup 6792 / renderPdfChips 6809 / renderPdfStats 6819 / renderPdfs 6838 / clearPdfFilter 6876 / loadPdfs 6882 / initPdfToolbar 6892 / truncate 6929。
- pdf 域纯件已迁 fx/pdf.js（19 函数）：pdfChipRowHTML / pdfRowHTML / pdfDetailHTML / pdfStatsText / pdfTrashConfirmHTML 等——本票胶水经 import 调用，调用点零改动。
- truncate 6929（`function truncate(text, n)` 文本截断）：迁移到 fx/core.js（通用件）并补测试（新 tests/js/truncate.test.mjs 或并入既有 core 测试文件——实施时按既有文件组织裁定）；登记 fx-guard DOMAINS。
- markup：tab-pdf @1882-1907；工具栏/表格/统计/详情/trash 弹窗容器 id 全部不动。
- host 页签分发器 import loadPdfs；启动 init 无 pdf init*（initPdfToolbar 由分发器/或既有调用处）。

## 检查表

- [ ] 新建 `static/js/ui/pdf.js`：15 个胶水函数逐字搬移 + import（app.js / fx/pdf.js / fx/core.js（esc））+ export（loadPdfs / initPdfToolbar 等）+ 头部注释
- [ ] fx/core.js：新增 truncate 纯函数（逐字搬移）+ export + window 桥追加名；fx-guard.test.mjs DOMAINS 登记 1 名
- [ ] 新 tests/js/truncate.test.mjs（或并入既有测试文件）：2-3 条断言（截断长度 / 省略号 / n<3 边界——以函数体实际契约写）
- [ ] index.html：CRLF 感知行区间删除（6648-6935 内 16 名；**物理升序**）+ 顶部 import 行追加（app.js 在本票前已引，追加 pdf.js）
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + PDF tab 实况探针（loadPdfs 后行数 > 0）
- [ ] grep 零残留：index.html 无 `function truncate(` / `function loadPdfs(` 等 16 名定义
- [ ] 中文提交

## 风险点

- copyPdfPath / confirmTrashPdf 用 `$` 与 handle/apiPost——随迁 import 即可；若引 `toast` 同理。
- truncate 若被多个域引用（grep 确认），core.js 单源后各引用方 import（fx 模块间允许）。
