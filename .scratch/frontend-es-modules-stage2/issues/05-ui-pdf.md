# 05 — PDF tab：static/js/ui/pdf.js + truncate 入 fx 补测

**要做什么：** PDF 资料库 tab 全部 DOM 胶水迁入 `static/js/ui/pdf.js`（列表渲染/统计/过滤器/详情弹窗/trash 弹窗/翻页加载/路径复制/工具栏 init）；顺带把**未测纯函数 truncate** 迁入 fx/core.js 并补轻量单测（用户已批：未测纯函数迁 fx + 补测）。

**被谁阻塞：** 02（app.js）

**状态：** resolved（2026-08-27；JS 442 全绿（440+2 新增）、pytest 2465 全绿、diag 零 EXC、smoke 11/11、探针 05 通过）

## 实施记录

- **物理位置修正**：pdf 区段实为 6587-6860（dashes header「PDF 资料库页：素材库全量 PDF 浏览」→ initPdfToolbar 末 `}`），上一票后偏移；**truncate 不在 pdf 区**——位于题库簇物理区内（原 6872，紧接 topicRows/topicPdfFile 状态之后、topicArchiveLoaded 之前），且 **grep 确认零调用方（死件）**。契约照迁（text 转字符串 / ≤n 原样 / slice(0,n)+"…"）。
- **static/js/ui/pdf.js**（新建 ~330 行）：15 个胶水函数 + 4 个状态（pdfUI 常量 / pdfFilterContext / pdfCache / pdfSearchTimer）+ pdfPageCache；import app.js（$/apiGet/apiPost/toast）+ fx/core.js（esc）+ fx/pdf.js（15 名：pdfEncodedPath/pdfHealth/pdfBroken/pdfFilterEntries/pdfSortEntries/pdfStats/pdfStatsText/pdfChipRowHTML/pdfRowHTML/pdfPagesUrl/pdfPagesText/pdfDetailHTML/pdfTrashUrl/pdfDupRemainText/pdfTrashConfirmHTML）；export 仅 loadPdfs/initPdfToolbar（host 分发器 + 启动 init 需求面）。
- **static/js/fx/core.js**：truncate 追加 + window 桥；DOMAINS core.js 块 4→5 名。
- **tests/js/truncate.test.mjs**（新建，2 test / 5 断言）：长度内原样 / 超长截断+省略号 / n=0 只留「…」/ 非字符串转字符串。
- **index.html（apply-05.mjs 一次通过，8272→8001）**：①host import `import { loadPdfs, initPdfToolbar } from "/js/ui/pdf.js";`（master.js 行后）；②pdf 区段（dashes → initPdfToolbar `}`）→4 行注记——搬移前校验含 8 哨兵名且**不含「赛题库页」（防越界进题库）**；③truncate 函数体（def → 首个裸 `}`）→1 行注记——校验体内含省略号与 `text.length <= n`。ⓘⓘ 校验：21 名零残留（含 pdfUI/pdfCache/pdfSearchTimer/pdfPageCache 等状态）、host 调用点 loadPdfs();/initPdfToolbar(); 仍在、「赛题库页」头注释仍在。
- 验证：node --test 442 全绿；pytest 2465 全绿（bg 确认）；diag 零 EXC；smoke 11/11；探针 probe-05-pdf.mjs：模块导出面 ✓ window.truncate 桥 + 实算 "abcde…" ✓ host 无 3 定义 ✓ **pdf tab 实况渲染 67 行 + pdf-msg 空 + 工具栏容器在位** ✓。

## 检查表

- [x] `static/js/ui/pdf.js`：15 胶水 + 状态逐字搬移 + export（loadPdfs/initPdfToolbar）+ 头部注释
- [x] `static/js/fx/core.js`：truncate + 桥 + DOMAINS 登记
- [x] `tests/js/truncate.test.mjs`：2 test / 5 断言
- [x] index.html：apply-05.mjs（CRLF 感知；区段删除 + 死件删除 + import 行；越界钩子防吞题库）+ 21 名零残留
- [x] node --test 442 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + 探针 05（pdf 67 行）通过
- [x] 中文提交 + CHANGELOG 记录

## 风险点 / 跟踪

- truncate 无调用方（当前）；若后续新增调用点，各引用方从 fx/core.js import（fx 模块间允许）。
- 题库簇（工单 09）迁出时，「truncate 已迁」注记行一并清理（记录在工单 09）。
