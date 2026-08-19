# 03 — README、摘要与交接输出

**要做什么：** 生成结果能够把评分点清单带到学生实际使用的工程资料中：README、生成结果摘要和交接提示词均展示同一份评分点数据；没有评分点时既有输出保持不变。

**被谁阻塞：** 02 — 推荐链路接线与兼容。

**状态：** resolved

- [x] README 增加评分点验收清单，按题面顺序展示描述、分值、分区和句号引用。
- [x] 生成结果摘要包含评分点信息，且使用推荐结果中的同一份结构化数据。
- [x] 交接提示词包含完整评分点信息；空引用明确显示未关联原文。
- [x] 评分点缺省或为空时不新增空章节、不改变既有文件内容与摘要格式。
- [x] 增加 README、摘要和交接提示词的确定性渲染测试，覆盖缺省兼容。

## 测试 seam

- `readme.render_readme` 纯函数：断言评分点章节的确定性渲染与缺省逐字节兼容。
- `generator.generate_project` 流程 seam：断言同一份评分点落入工程根 README 与返回摘要。
- `webapp._generation_result` 薄响应 seam：断言生成摘要 JSON 带可选评分点，空清单不落键。
- 前端 Handoff 纯函数 seam：从 `index.html` 抽取评分点格式化函数，用 node:test 断言完整清单与空引用文案；前端展示卡片留给 04。

## 实施说明

评分点沿推荐结果的 `score_points` 结构进入生成请求，后端用同一解析器做可选降级后透传给 `generate_project`；`GenerationSummary`、`README.md`、生成结果摘要 JSON 与 Handoff 均消费同一份结构化数据。README 与 Handoff 只在评分点非空时新增评分点章节；生成结果摘要只在非空时落 `score_points` 字段，空清单保持旧载荷形状。

前端新增 `formatScorePoints` 纯函数供生成摘要和 Handoff 共用；题面变化或重新推荐会清空旧评分点，避免旧题评分清单串入新工程。推荐结果区域的只读展示仍按 04 工单处理。

## 测试结果

- `python -m pytest -q`：1982 passed（3 warnings，均为既有 warning）
- `python -m mypy src`：通过（52 source files）
- `node --test tests/js/*.mjs`：34 passed
- `git diff --check`：通过
- 代码评审：Standards / Spec 双轴复核无 blocker；第一次 Spec 评审指出 Handoff 空评分点不应新增章节，已修复并补 `scoreSection` 断言。
