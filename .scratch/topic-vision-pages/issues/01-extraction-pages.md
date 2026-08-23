# 工单 01：extraction.py 页范围定位与提取（locate_topic_pages + pages 参数）

Status: resolved
Depends: 无
Blocks: 02

## 目标

共享 PDF 赛题补图注的基础能力：题面页定位 + 限定页范围提取。

## 改动点（src/contest_generator/extraction.py + tests/test_extraction.py）

1. 新函数 `locate_topic_pages(pdf_path: Path, topic_text: str) -> tuple[int, int] | None`：
   - 题面独特文本 = topic_text 去空白后前 LOCATE_TOPIC_SAMPLE_CHARS（新常量，如 20）
     字符；逐页 extract_text() 去空白后子串匹配；命中页 = 起始页，范围 =
     (start, start + LOCATE_TOPIC_SPAN_PAGES)（新常量，如 2）。
   - 坏 PDF / 空白题面 / 无命中 → None（绝不抛）。
2. `pdf_figure_annotations(path, pages: Sequence[int] | None = None)`：pages 限定扫描
   页（1-based）；None = 全部（现状）。实现：页循环前构造命中集合，跳过集合外页。
3. `pdf_image_notes(path, *, …, pages: Sequence[int] | None = None)`：同上过滤
   page.images 所在页（enumerate 页号 ∈ 集合）。
4. 常量：LOCATE_TOPIC_SAMPLE_CHARS / LOCATE_TOPIC_SPAN_PAGES（放 FIGURE_ANNOTATION_*
   常量区附近）。

## 测试（tdd 先红）

- 构造两页 PDF（文本层可搜）：第一页含题面独特句 + 图1 标注文字，第二页含另一题
  标注 —— locate_topic_pages 命中 (1, 2)；无命中 → None；空白题面 → None。
- pdf_figure_annotations(pages=[1]) 只出第一页块（第二页「图2」不出）；pages=None
  两页都出（现状兼容）。
- pdf_image_notes(pages=[1]) 只调第一页图的视觉（FakeTransport 记录调用次数与页
  归属）；pages=None 全部（现状兼容）。
- 坏 PDF → locate 返回 None、pdf_figure_annotations 空串（防御既有行为）。

## 验收

- 单测全绿；既有 pdf_figure_annotations / pdf_image_notes 测试（无 pages 参数）
  零改动通过 = 向后兼容。
