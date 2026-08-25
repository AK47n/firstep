# 02 上传成功后展示 PDF 页图（前端）

> 归属 spec：`.scratch/upload-pdf-pages/spec.md`

Status: resolved

## 背景

工单 01 后 `/api/extract` 对 PDF 返回 `pages`/`total_pages`；前端上传成功分支仍显式隐藏页图。

## 任务

- `btn-upload` 成功分支（index.html:1866-1887）：`data.pages` 非空 → `setTopicPdfTextVisible(false)` + `showTopicPdfViewer(data)`；否则维持 `hideTopicPdfViewer()`。
- `showTopicPdfViewer`（index.html:1922）追加截断提示：`data.total_pages > data.pages.length` 时页图下方 muted 行「共 N 页，已显示前 M 页（其余页未展示）」。
- `data.pages` 缺省（非 PDF 上传）时行为不变。

## 验收标准

- [x] headless e2e：上传本地 PDF → `#topic-pdf-box` 可见、页图数量正确、文字框默认收起、`btn-topic-pdf-text` 可切回文字版、放大遮罩可用
- [x] 8 页 PDF 上传显示「共 8 页，已显示前 6 页」提示
- [x] 上传 txt 仍只显示文字（无页图区）
- [x] `node --test "tests/js/*.test.mjs"` 全绿；主 script 语法检查通过；截图目检
