# 工单 02：enrich_topic_image_notes 共享 PDF 走页范围定位 + 澄清提示词兜底

Status: resolved
Depends: 01
Blocks: 无

## 目标

共享 PDF 赛题也能安全补图注（2021F 图1 落地）；AI 在无图时不再反问用户要图。

## 改动点

1. **src/contest_generator/topic_library.py `enrich_topic_image_notes`**：
   - 共享 PDF（shared_pdf > 1）分支从「整体跳过」改为「定位 + 页范围提取」：
     `locate_topic_pages(pdf_path, entry.problem_text)` → None = 跳过；命中 →
     `pdf_figure_annotations(pdf_path, pages=范围)` 文字标注优先 → 空则
     `pdf_image_notes(…, pages=范围)` 视觉兜底 → 仍空原样返回。
   - 非共享 PDF 保持现状全文档扫描（最小回归面）。
   - 幂等 / 不抛 / 写回 + commit_after_write 契约不变。
2. **src/contest_generator/llm.py CLARIFY_SYSTEM_PROMPT**：加兜底句——题面引用图但
   无图描述时，不要求用户补充图内容；基于题面文本已有标注（尺寸/位置文字）推断并
   说明假设；只有影响核心决策的缺失信息才提问。

## 测试（tdd 先红）

- topic_library：构造共引 PDF（两题各一页各带「图1」标注）+ 两条目共享 original_pdf →
  enrich 后题面只含本页 `[图N 标注]` 段、不含另一题标注（2024H 污染场景回归）；
  定位失败（题面文本不在 PDF）→ 原样返回不写回；非共享 PDF 全文档行为不变（既有
  测试保持绿）。
- llm：CLARIFY_SYSTEM_PROMPT 契约测试（含兜底句关键字）。
- 实测：GET /api/topics/2021F 触发补图注 → topic.md 出现 `[图1 标注：…]`（文字标注
  零额度；2021F 真题汇总 PDF 真实验证）。

## 验收

- 全量 pytest 绿 + mypy src 干净；2021F topic.md 真实出现图1 标注；重新推荐时
  clarify 不再问「看不到图」。
