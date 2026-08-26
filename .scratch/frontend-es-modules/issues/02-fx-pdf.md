# 02 — pdf 域模块化：fx/pdf.js（21 函数）

**要做什么：** pdf 资料库全部被测试纯函数迁入 `static/js/fx/pdf.js`，pdf-library.test.mjs 由字符串提取改为 import；页面 PDF tab 行为零变化。

**被谁阻塞：** 01（基础设施 + core.js 的 esc/formatSize 先行）

**状态：** ready-for-agent

- [ ] 新建 fx/pdf.js：pdfSubdir / formatMtime / pdfEncodedPath / pdfBadgeTags / pdfBroken / pdfDupGroups / pdfFilterEntries / pdfSortEntries / pdfStats / pdfHealth / pdfStatsText / pdfRowHTML / pdfChipRowHTML / pdfPagesUrl / pdfPagesText / pdfDupRemainText / pdfDetailHTML / pdfTrashUrl / pdfTrashConfirmHTML 及域内常量；esc/formatSize 从 fx/core.js import；尾部 window 桥
- [ ] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/pdf.js">`
- [ ] pdf-library.test.mjs：删 html 读入与 extract()，改 import（从 fx/pdf.js 与 fx/core.js）
- [ ] `node --test "tests/js/*.test.mjs"` 全绿（基线 416）；冒烟 PDF tab
