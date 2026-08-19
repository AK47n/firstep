# 04 — 前端展示与回归收口

**要做什么：** 学生在推荐结果区域可以只读查看评分点，并能在旧推荐载荷、无评分表和评分点解析失败时继续完成后续步骤；全链路测试确认新增信息不会阻断原有生成流程。

**被谁阻塞：** 03 — README、摘要与交接输出。

**状态：** resolved

- [x] 推荐结果区域与功能需求、模块推荐结果并列展示评分点，不新增主流程步骤。
- [x] 展示评分点的分区、分值、描述和句号引用；空引用显示未关联原文。
- [x] 评分点区域只读，不增加编辑或回写请求。
- [x] 旧载荷没有评分点字段时不显示异常空面板，后续步骤可正常操作。
- [x] 无评分表、评分点为空和评分点解析失败时，现有推荐与生成流程继续可用。
- [x] 运行推荐、生成、README、前端和全量回归测试，记录验收结果。

## 实施说明

推荐结果区域新增只读评分点面板，复用既有 `formatScorePoints` 文案：有评分点时在功能需求卡片前展示分区、分值、句号引用和描述；旧载荷缺字段、无评分表或空清单时不渲染空面板，后续选择模块、生成和交接流程保持原样。展示文本统一转义，面板不包含输入控件或回写请求。

## 测试结果

- `node --test tests/js/score-points-format.test.mjs`：9 passed
- `node --test tests/js/*.mjs`：38 passed
- `python -m pytest -q tests/test_selection.py tests/test_webapp.py tests/test_readme.py tests/test_generator.py`：422 passed（1 个既有 warning）
- `python -m pytest -q`：1982 passed（3 个既有 warning）
- `python -m mypy src`：通过（52 source files）
- `git diff --check`：通过（仅提示既有 Windows 行尾替换 warning）
- 代码评审：Standards / Spec 双轴复核无 blocker。
