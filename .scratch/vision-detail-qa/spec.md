# 问答式精注记（vision-detail-qa）

## 问题陈述

上传赛题 PDF / 图片后，视觉通道把图转译成一段文字描述（`[示意图N：…]` 或图片描述）。图→文字的单轮转译存在系统性信息损耗：数字标注与单位、型号字符串、颜色与线型（如"红色实线"）、引脚号、元件位置关系往往被模型省略或概括。这些细节恰是电赛解题的关键，丢失后进入题面简介 / AI 推荐 / 骨架，下游全链路都会"看不见"。

现状只有一轮"看图→描述"，没有让模型回头补细节的机制。

## 方案

**问答式精注记**：对每张已产出描述的图，追加一轮视觉追问——把第一轮描述连同原图再发给视觉模型，提示只补充第一轮遗漏的具体细节（数字标注 / 型号 / 颜色线型 / 引脚号 / 位置关系）；模型判定无遗漏时回复「无补充」则不合并。产出仍是纯文字（`[示意图N：<描述>；细节补充：<…>]`），可编辑、可跨会话、下游零改动。

- 默认开启；设置页「视觉通道」区加开关，省钱用户可关。
- 成本：每张图 +1 次视觉调用（第一轮命中缓存的不受影响——第二轮 prompt 不同，缓存键独立，必付）。
- 降级原则：第二轮失败 / 空回复 / 否定回复 → 返回原描述，绝不抛（与"视觉是增强不是阻塞"一致）。

## 用户故事

- 作为用户，上传含电路图的赛题 PDF 后，图注中能看到"电阻 R1 10kΩ、红色实线连接、引脚 PA1"这类细节，而不只是"一个电路图"。
- 作为省钱用户，在设置页关掉「问答式精注记」后，上传抽取不再发起第二轮视觉调用（第一轮照旧）。
- 作为题库维护者，重新取题面 / 拆条入库的图注同样带精注记，且开关与上传路径一致。

## 实现决策

1. 核心放 `src/contest_generator/extraction.py`：新增 `refine_image_description(data, mime, description, *, vision_base_url, vision_api_key, vision_model, observation_collector=None) -> str`，与 `_describe_kwargs` 同层，三处视觉描述调用点（pdf_image_notes / pdf_page_render_notes / extract_image）复用。
2. 新增模块常量：`DETAIL_QA_PROMPT`（追问提示词模板，含第一轮描述）与 `DETAIL_QA_NO_SUPPLEMENT`（否定词元组：无补充 / 无需补充 / 没有补充 / 无更多 等，命中 → 不合并）。
3. `detail_qa: bool = True` 参数线程：`pdf_image_notes` / `pdf_page_render_notes` / `extract_image` / `extract_pdf_with_image_notes` / `enrich_topic_image_notes`（topic_library.py）全量传入；`False` 时完全不发起第二轮调用（行为与现状逐字节一致）。
4. 渲染页图注（pdf_page_render_notes）精注记放在"图文过滤通过之后、写回之前"——无图页 / 正文页误描述在过滤阶段就跳过，不付第二轮调用。
5. 配置：`config.py` 新增 `vision_detail_qa: bool = True`（解析校验同 recommend_cache_enabled 模式：非 bool → ConfigError）。
6. webapp.py：`/api/extract`（图片 + PDF 两分支）、`/api/topics/split`、取题面增强（enrich_topic_image_notes 调用点）三处传 `detail_qa=config.vision_detail_qa`；`/api/settings` GET 回 `vision_detail_qa`、PUT 用 `_optional_bool(payload, "vision_detail_qa", default=True)` 解析。
7. 前端 `index.html`：设置页视觉通道区加 `<input type="checkbox" id="set-vision-detail-qa">`（样式同 set-recommend-cache）；加载 `s.vision_detail_qa !== false`（旧 state 缺字段默认开）；保存 payload 加 `vision_detail_qa: $("set-vision-detail-qa").checked`。
8. `describe_image_cached` 缓存键 = 图片 + prompt 联合 sha256：二轮 prompt 与一轮不同，天然独立缓存，互不串答案（无需额外改动）。

## 测试决策

- `tests/test_extraction.py`：`refine_image_description` 四用例——①二轮有细节 → 合并成 `描述；细节补充：…`；②二轮抛异常 → 返回原描述；③二轮回复「无补充」→ 返回原描述；④`detail_qa=False` 时 extract_image / pdf_image_notes 只调一次 describe（计数断言）。
- `tests/test_config.py`：`vision_detail_qa` 解析默认 True、非 bool 报 ConfigError。
- `tests/test_webapp.py`：设置 PUT/GET 往返 `vision_detail_qa`；extract 图片分支 `detail_qa=False` 时 describe 只调一次。
- 回归：pytest 全量 + `node --test tests/js`（前端仅设置页改动，无新 JS 纯函数）。

## 范围外

- 推荐阶段的"图内问答"（vision_qa.py answer_figure_question，recommend-vision-qa/02）不动——它是另一功能。
- 不为精注记第二轮做专门缓存透出 / 用量统计拆分（走既有 observation_collector 通道，自然计入 vision-describe）。
- 不改变图注段格式前缀（`[示意图N：` / `[图N 标注：`），下游与幂等正则零感知。
