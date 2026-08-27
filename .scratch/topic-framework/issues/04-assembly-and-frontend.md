# 04 — webapp 装配 + 前端（骨架注入提示 + 参考库题型列/下拉）

**要做什么：** 装配缝：`webapp /api/skeleton` 在 `_assemble_topic_context` 后、`run_skeleton` 前计算 `framework`——遍历 `topic.references`（保序，含手动条目——手动选参考也可能带题型框架，与全文注入同语义），取第一个 `topic_type` 非空且平台匹配（`_platform_matches`，any 全进 / 空 = 不过滤）的条目 → `build_topic_framework`；注入 `run_skeleton(..., topic_framework=framework)`；返回体加 `topic_framework: {"topic_type", "source", "injected": true/false}`（None 时 `{"injected": false}`）。GET /api/references 响应加 `topic_types`（词表一次带出，前端下拉单源）。前端：参考库表格加「题型」列（词表空 = "—"）+ 编辑弹窗加「题型」下拉（选项 = "" 未标记 + 词表，PUT payload 带 topic_type）+ 新增表单同款下拉；生成页步骤 8 骨架面板加「题型框架已注入：<topic_type>（来源 <entry.title>）」提示行（injected 为真才显示）；纯函数入 fx、DOM 胶水入 ui（迁移规则照旧）。

**被谁阻塞：** 01（字段）、02（读取）、03（协议贯通）。

**状态：** resolved

**验收：** 全部 ✓（`_topic_framework_info` 装配（平台过滤 / 保序首个 / 降级）+ `POST /api/skeleton` 返回体带 `topic_framework` + `GET /api/references/topic-types` 端点；前端参考库表格「题型」列 + 编辑弹窗/录入表单「题型」下拉 + 生成页步骤 8「题型框架已注入」提示行（`frameworkNoteHTML` 入 fx/generate.js）；JS 492 全绿 + 后台 webapp 集成测试 3 条 + E2E 实跑全绿）。

- [ ] `/api/skeleton` 装配 framework（保序取首个平台匹配 + topic_type 非空；`build_topic_framework` None = 降级 injected false）+ 透传 + 返回体带 `topic_framework`（null 时 `{"injected": false}`）
- [ ] GET /api/references 响应附 `topic_types`（词表；单源 dropdown+校验同源）
- [ ] 参考库表格「题型」列（topic_type 空 = "—"）+ 编辑弹窗「题型」下拉（含 "（未标记）" 项）+ 新增表单同款下拉；PUT / POST payload 带 topic_type
- [ ] 生成页步骤 8：骨架结果面板「题型框架已注入」提示行（纯函数 `frameworkNoteHTML(data)` 入 fx，DOM 胶水入 ui/generate-mainc.js）
- [ ] 测试：/api/skeleton 假 LLM 命中框架条目（21F → injected true + source 断言）/ 无标记条目 → false；前后端纯函数（题型下拉 / 列渲染 / 提示行）；fx-guard 登记新纯函数
