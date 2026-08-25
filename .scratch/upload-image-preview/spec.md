# 图片上传显示原图（upload-image-preview）— spec

## 问题陈述

上传图片（png/jpg/jpeg/bmp/webp/gif）只有视觉模型输出的文字描述，看不到原图。用户确认做 ②：**图片上传直接显示原图**（docx 仍只出文字）。

## 方案

### 后端（extraction.py + webapp.py）

- extraction.py 新增 `image_data_url(path) -> str | None`：读取文件字节 → `data:<mime>;base64,…`（`mimetypes.guess_type` 判 mime；读失败 → None）。图片 ≤ `MAX_IMAGE_BYTES`（4MB，extract_image 已拒超限），base64 化本地可接受。
- webapp.py `/api/extract` 图片分支：返回 `{"text": …, "image_data_url": …}`；PDF/其他分支不动。

### 前端（index.html）

- 第 1 步卡新增 `#topic-image-box`（hidden）：`#btn-topic-image-text`（显示文字版/收起文字版切换）+ `#topic-image-view` 单图（点击放大走既有 `#pdf-zoom` 遮罩——它是通用图片放大，改名无关）。
- `setTopicPdfTextVisible(visible, btn?)` 增加可选按钮参数（默认 `#btn-topic-pdf-text`，既有调用不变）：图片模式按钮也要能翻转文案。
- `btn-upload` 成功分支三态：`data.image_data_url` → 原图箱；`data.pages` → PDF 页图箱；都没有 → 只显示文字。
- `hideTopicPdfViewer()` 增隐藏 `#topic-image-box`（手动改题面/粘贴后旧图不残留）；`showTopicPdfViewer` 增隐藏图片箱（取题面与图片上传互斥）。
- 图片上传后文字框默认收起（页图模式），同 PDF 语义。

## 用户故事

- 作为用户，上传图片后能看到原图（可点击放大），文字描述仍在文字框里（AI 输入不变）。
- 作为用户，上传 PDF / txt 行为不变。

## 测试决策

`tests/test_webapp.py` 新增用例（monkeypatch `extraction_mod.describe_image_cached` 假描述，1×1 真实 PNG 字节）：200、text=假描述、`image_data_url` 前缀 `data:image/png;base64,`、**解码后与原字节完全一致**（无损）。

前端 headless e2e：上传 PNG → `#topic-image-box` 可见、img src 正确、文字框默认收起、`btn-topic-image-text` 可切回；截图目检。

## 范围外

- docx 页图/预览（无分页渲染管线，不做）。
- 图片缩放/压缩预览（保持原图无损；超大图由 4MB 上限兜底）。
- 修改既有 PDF 页图路径（不动）。
