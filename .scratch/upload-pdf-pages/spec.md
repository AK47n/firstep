# 上传 PDF 显示页图（upload-pdf-pages）— spec

## 问题陈述

用户问：「第一步我上传的 PDF 能正常显示 PDF 吗，还是只有去题库能显示？」——现状只有题库「取题面」有原题 PDF 页图展示（`GET /api/topics/<key>/pages`，webapp.py:2563），上传路径（`POST /api/extract`，webapp.py:859）只返回抽取文本，前端成功分支显式 `hideTopicPdfViewer()`（index.html:1877）——上传的 PDF 看不到页面渲染。用户确认做 ①：**上传 PDF 也显示页图**（与 AI 管线无关，纯展示；已向用户解释 AI 识别图片走视觉→文字注记，不受影响）。

## 方案

### 后端（extraction.py + webapp.py）

- extraction.py 新增 `render_pdf_pages(pdf_path: Path, max_pages: int = 6) -> list[dict]`：PyMuPDF 渲染前 max_pages 页 → `[{page_no, data_url}]`（base64 PNG data URL，复用同文件 `_render_page_png` 渲染——与题库 `/pages` 端点同款；单页失败跳过；整体失败/无 PyMuPDF → 空列表，不抛错不阻塞）。
- webapp.py `/api/extract` PDF 分支：返回值改为 `{"text": …, "pages": render_pdf_pages(tmp_path), "total_pages": N}`；`total_pages` 来自 fitz `doc.page_count`（渲染失败时为 pages 长度兜底）。
- docx/txt/md/图片返回值不变（`{"text": …}`，无 pages 字段）。

### 前端（index.html）

- `btn-upload` 成功分支（index.html:1866-1887）：`data.pages` 非空 → 收起文字版（`setTopicPdfTextVisible(false)`）+ `showTopicPdfViewer(data)`（与题库同款：页图叠放、点击放大、可切文字版）；缺页图（非 PDF / 渲染失败）→ 维持现状 `hideTopicPdfViewer()`。
- `showTopicPdfViewer` 追加截断提示：`data.total_pages > data.pages.length` 时页图下方加一行 muted「共 N 页，已显示前 M 页（其余页未展示）」。（/pages 端点无 total_pages 字段，不受影响。）

## 用户故事

- 作为用户，上传 PDF 后能看到原题页面渲染图（与题库取题面一致的外观与交互），可点击放大、可切换文字版；页数 >6 时明确提示只显示前 6 页。
- 作为用户，AI 识别行为不变（推荐/简介/骨架/生成只认文字框；图片识别仍走视觉→图注文本）。

## 实现决策

1. 页数上限 6：上传 PDF 可能数十页，全量渲染 base64 会拖慢响应；题库定位题面页（≤2 页 span），上传无定位锚点，取前 6 页 + 截断提示折中。
2. 复用 `_render_page_png`（extraction.py:330，`webapp.py:73` 已以 `render_page_png` 别名导入）——渲染参数、失败降级语义一致，不新开渲染路径。
3. 渲染放在临时文件删除前（`finally tmp_path.unlink` 之前 return 前完成）——`render_pdf_pages(tmp_path)` 在同一 try 块内调用。
4. 前端不改 AI 下游任何逻辑；页图展示与题库共用 `showTopicPdfViewer`（含放大遮罩 `#pdf-zoom`）。

## 测试决策

`tests/test_webapp.py`（/api/extract 既有测试旁，client 夹具 + `make_multi_page_pdf` 手工构造 PDF，fitz 真实渲染——与 test_topic_library /pages 测试同款范式）：

- 2 页 PDF → 200，text 含正文，`total_pages == 2`，pages `[1, 2]`，data_url 为真实 PNG（魔数断言）。
- 8 页 PDF → pages 长度 6（上限），`total_pages == 8`。
- 无 PyMuPDF / 渲染全失败 → `render_pdf_pages` 返回 `[]`（monkeypatch `_render_page_png` 为 None 时 /api/extract 仍 200 且无 pages 键或空数组）。

前端 headless e2e：`DOM.setFileInputFiles` 设置 `#problem-file` → 点 `btn-upload` → 断言 `#topic-pdf-box` 可见、`#topic-pdf-pages img` 数量 = 页数、文字框隐藏、`btn-topic-pdf-text` 可切回；截图目检。

## 范围外

- 图片上传显示原图（选项 ②）——另立。
- docx 页图渲染——docx 无分页渲染管线，不做。
- AI 下游直通视觉（绕开文字转译）——架构级，另立 spec。
- 题库 `/pages` 端点行为不变。
