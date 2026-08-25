# 01 /api/extract 图片上传回传原图（后端）

> 归属 spec：`.scratch/upload-image-preview/spec.md`

Status: resolved

## 背景

图片上传只有文字描述、无原图（用户确认做 ②）。

## 任务

- extraction.py 新增 `image_data_url(path) -> str | None`（mime + base64；失败 None）。
- webapp.py `/api/extract` 图片分支：返回 `{"text": …, "image_data_url": …}`。

## 验收标准

- [x] `tests/test_webapp.py` 新增用例绿（1×1 PNG → 200 + 原图无损回传）
- [x] `python -m pytest tests/test_webapp.py` 全绿
- [x] PDF / 文本分支响应不变（既有 extract 用例仍绿）
