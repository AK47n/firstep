# 02 — pdf 域模块化：fx/pdf.js（21 函数）

**要做什么：** pdf 资料库全部被测试纯函数迁入 `static/js/fx/pdf.js`，pdf-library.test.mjs 由字符串提取改为 import；页面 PDF tab 行为零变化。

**被谁阻塞：** 01（基础设施 + core.js 的 esc/formatSize 先行）

**状态：** resolved（2026-08-26；JS 416 全绿 + 浏览器冒烟 11/11）

## 实施记录

- fx/pdf.js：19 个纯函数（pdfEncodedPath / pdfSubdir / formatMtime / pdfBroken / pdfBadgeTags / pdfDupGroups / pdfHealth / pdfFilterEntries / pdfSortEntries / pdfStats / pdfStatsText / pdfChipRowHTML / pdfRowHTML / pdfPagesUrl / pdfPagesText / pdfDetailHTML / pdfTrashUrl / pdfDupRemainText / pdfTrashConfirmHTML）；esc/formatSize import 自 fx/core.js；尾部 window 桥。
- 主体 module 顶部 import 行追加；index.html 删除 19 个定义；pdfFileUrl / pdfHealthPredicates / pdfTrashDate / pdfPageCache / loadPdfPages / copyPdfPath / showPdfDetail / confirmTrash* / openPdfTrashConfirm 等胶水留内联（domain 边界：只搬被测试纯函数）。
- pdf-library.test.mjs：提取段整体换 import（含原「依赖顺序」注释删除）。
- 教训：index.html 大块 edit 时误留「function renderPdfChips() {」悬空签名 → 主体 module SyntaxError（Unexpected end of input）→ 冒烟 7 项假失败 → 撤除后恢复。后续工单编辑后必跑浏览器 diag（.scratch/frontend-es-modules/diag.mjs）验证零 EXC。

- [x] 新建 fx/pdf.js：pdfSubdir / formatMtime / pdfEncodedPath / pdfBadgeTags / pdfBroken / pdfDupGroups / pdfFilterEntries / pdfSortEntries / pdfStats / pdfHealth / pdfStatsText / pdfRowHTML / pdfChipRowHTML / pdfPagesUrl / pdfPagesText / pdfDupRemainText / pdfDetailHTML / pdfTrashUrl / pdfTrashConfirmHTML 及域内常量；esc/formatSize 从 fx/core.js import；尾部 window 桥
- [x] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/pdf.js">`
- [x] pdf-library.test.mjs：删 html 读入与 extract()，改 import（从 fx/pdf.js 与 fx/core.js）
- [x] `node --test "tests/js/*.test.mjs"` 全绿（基线 416）；冒烟 PDF tab


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
