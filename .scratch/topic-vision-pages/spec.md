# Spec：共享 PDF 赛题补图注——页范围定位提取（2021F 图1 缺失根因修复）

## 问题（用户报告）

用户加载历史题面 2021F（智能送药小车），AI 澄清时问「题面引用了图1院区结构示意图，
但当前文本无法看到该图」。原因链：

1. 2021F 入库时无视觉通道，topic.md 是纯文本抽取——图1 从未被识别（只有散乱标注
   `60cm60cm60cm40cm 30cm 40cm…` 混在文本流）。
2. 系统已有补图注能力（`GET /api/topics/{key}` → `enrich_topic_image_notes`），但 2021F
   的原 PDF 是**真题汇总**（`000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf`，被
   2018C~2024H 共引）——共享 PDF 守卫（topic_library.py:232-243）刻意跳过：图注提取
   无页范围，全文档扫描会把其它题的图注污染进当前题面（2024H 曾踩坑追加约 280 行）。
3. 结果：共享 PDF 的赛题永远补不上图注；AI 看不到图、如实反问用户要图描述（用户没有
   更详细的图，反问无解）。

## 方案：定位题面页 → 限定页范围提取

1. **extraction.py 新函数 `locate_topic_pages(pdf_path, topic_text) -> tuple[int, int] | None`**：
   题面独特文本（去空白后前 N 字符）在 PDF 各页文本层搜索 → 找到的页起 2 页范围
   （图紧跟正文第 1~2 页）；找不到（扫描件无文本层 / 文本不匹配）→ None。
2. **`pdf_figure_annotations(path, pages: Sequence[int] | None = None)`**：
   pages（1-based）限定扫描页；None = 全部（现状逐字节不变）。
3. **`pdf_image_notes(path, ..., pages: Sequence[int] | None = None)`**：
   同上（视觉兜底按页过滤 page.images）。
4. **topic_library.py `enrich_topic_image_notes`**：共享 PDF 分支不再整体跳过——
   定位题面页 → 页范围内文字标注（零额度）优先 → 空则视觉兜底 → 仍空原样返回。
   非共享 PDF（单条目专属）保持现状全文档扫描（最小回归面）。
5. **llm.py CLARIFY_SYSTEM_PROMPT 兜底句**：题面引用图但无图描述时**不要求用户补充
   图内容**——基于题面文本中已有的标注信息（尺寸/位置文字）推断并说明假设；只有
   影响核心决策的缺失信息才提问（2021F 图1 的 60cm/40cm/30cm 标注已在文本中）。

## 边界与守卫

- 定位失败（文本不匹配）→ 跳过（宁可没有图注，不冒险）。
- 页范围只收自己题的图注——别的题的「图1」不在本页范围，天然隔离（2024H 污染场景消除）。
- 幂等（已含 `[示意图` / `[图N 标注` 跳过）、不抛、视觉失败降级——既有契约不变。
- 补图注成功后 topic.md 写回 + commit_after_write 自动提交（既有行为）。

## 验收

- 单元：locate_topic_pages 找到/找不到；pdf_figure_annotations/pdf_image_notes pages
  限定与 None 兼容；enrich 共享 PDF 只收本页图注（构造两题共引 PDF 验证）；非共享
  现状不变。
- 契约：CLARIFY_SYSTEM_PROMPT 含兜底句（提示词契约测试）。
- 全量 pytest 绿 + mypy src 干净。
- 实测：GET /api/topics/2021F 触发补图注 → topic.md 出现 `[图1 标注：…]`（真实 PDF
  验证，文字标注零额度优先）。
