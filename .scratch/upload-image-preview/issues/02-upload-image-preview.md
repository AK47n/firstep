# 02 图片上传原图展示（前端）

> 归属 spec：`.scratch/upload-image-preview/spec.md`

Status: resolved

## 背景

工单 01 后 `/api/extract` 图片上传返回 `image_data_url`；前端只显示文字。

## 任务

- 第 1 步卡新增 `#topic-image-box`（hidden）：`#btn-topic-image-text` + `#topic-image-view`（点击放大走 `#pdf-zoom`）。
- `setTopicPdfTextVisible(visible, btn?)` 加可选按钮参数（默认 `#btn-topic-pdf-text`）。
- `btn-upload` 成功分支三态（原图 / PDF 页图 / 仅文字）；`hideTopicPdfViewer` 与 `showTopicPdfViewer` 互斥隐藏图片箱。

## 验收标准

- [x] headless e2e：上传 PNG → 图片箱可见、img src 正确、文字框收起、按钮可切回、放大遮罩可用
- [x] 上传 txt 仍只显示文字；上传 PDF 页图行为不变
- [x] `node --test "tests/js/*.test.mjs"` 全绿；主 script 语法检查通过；截图目检
