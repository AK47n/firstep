# 01 /api/extract 返回上传 PDF 页图（后端）

> 归属 spec：`.scratch/upload-pdf-pages/spec.md`

Status: resolved

## 背景

上传 PDF 只有抽取文本、无页图（用户反馈）。后端渲染能力现成（`_render_page_png`，题库 /pages 同款）。

## 任务

- extraction.py 新增 `render_pdf_pages(pdf_path, max_pages=6) -> list[dict]`（`{page_no, data_url}` base64 PNG；复用 `_render_page_png`；失败跳过/降级空列表；新增 `import base64`）。
- webapp.py `/api/extract`（webapp.py:859）PDF 分支：返回 `{"text": …, "pages": …, "total_pages": N}`；非 PDF 分支不动。

## 验收标准

- [x] `tests/test_webapp.py` 新增用例绿（2 页 PDF 文本+页图、8 页 PDF 截断 6 页、渲染失败降级）
- [x] `python -m pytest tests/test_webapp.py` 全绿
- [x] 非 PDF 上传响应不变（既有 extract 用例仍绿）
