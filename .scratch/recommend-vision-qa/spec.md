# Spec：推荐阶段按需视觉问答（vision-qa-on-demand）

## 问题陈述

取 2021F 赛题（库内条目，题面带图1）走 AI 推荐时，AI 因题面文字未给出走廊宽度、各段走廊长度、药房和病房门口区域的精确尺寸，反问用户「请提供完整的院区尺寸图」。用户预期：图1 明明在赛题 PDF 里，系统应当自动看图回答这类「图内信息」问题，而不是回头问人。

现状根因（已排查确认）：

- 库条目图注（`[图1 标注：…]`）是取题面时一次性生成的（`topic_library.enrich_topic_image_notes` 幂等，已有图注即跳过），质量靠单次视觉调用运气；2021F 的图注只把数字挂到大致位置、从无语义指代（走廊宽 30cm / 病房 60×40cm / 门口区域 5cm 一条都没写），还夹带幻觉（「甲乙丙丁」）。
- 题面正文混入 PDF 图内文字碎片（`60cm60cm60cm40cm…`），把下游 LLM 带偏。
- 澄清提示词（`CLARIFY_SYSTEM_PROMPT`）禁止 AI 问图内容，但留了口子「只有影响核心决策的缺失信息才提问」——21F 的尺寸影响核心决策（小车 ≤25×20×25cm vs 走廊 30cm 宽），AI 问了，严格说没违规，但体验上就是「视觉没干活」。

用户决策：不做「清碎片重跑图注」（A）或「改描述提示词」（B）的补丁，做**治本闭环**——推荐/澄清阶段检测到 AI 的问题属于「图内信息」时，不反问用户，自动把原 PDF 渲染图 + AI 的问题丢给视觉模型，把答案喂回澄清历史。

## 方案

在推荐编排（`selection.run_recommendation`）的澄清阶段引入「按需视觉问答」供给回调：

1. 澄清阶段 `llm.clarify` 返回待问用户的 questions 后，逐条机械判定是否属于「图内信息问题」（问题提到题面引用的图，且涉及尺寸/位置/走向等图上才有的事实）。
2. 命中的问题不直接问用户，交给视觉问答回调：渲染原 PDF 中题面所在页 → `describe_image_cached(png, "image/png", prompt=问题文本)` 让视觉模型针对性作答。
3. 视觉答出内容 → 该问题从「问用户」清单移除，答案作为澄清问答（user 问题 / AI 答案）并入 clarifications 历史，随收敛循环喂给模型；视觉答不上（未配置 / 无图 / 网络失败 / 模型回答「图上没有」）→ 该问题维持原样问用户。
4. 剩余 questions 照旧经 `question` 事件发出；全部被视觉消化 → 不打扰用户，直接带着澄清历史进收敛。

硬边界：只有库内条目（`TopicContext.key` 非空且条目带 original_pdf）才有原图可看；粘贴题面（no-topic 形）无图，维持原行为问用户。任何失败静默降级到现状，绝不阻塞、绝不比现在更打扰用户。

## 用户故事

1. 作为用户，当我取库内赛题（题面引用图）走推荐、AI 想确认图上尺寸时，我希望系统自动看图回答，以便我不被打断、推荐直接继续。
2. 作为用户，当图上确实没有 AI 问的信息、或视觉通道不可用时，我希望该问题照旧问到我，以便不丢失必要信息。
3. 作为用户，当我粘贴无图题面（未识别到库条目）时，我希望行为与现在完全一致（该问就问），以便不引入异常路径。
4. 作为用户，当我重复推荐同一题时，我希望相同图+相同问题的视觉答案命中缓存、不再重复花视觉调用额度，以便省钱提速。
5. 作为用户，我希望被自动回答的问题在最终推荐结果里可追溯（澄清历史可见），以便理解 AI 为什么这么选。

## 实现决策

- **触发点**：`selection.run_recommendation` 澄清门内，`llm.clarify` 返回 pending 之后、`emit.question` 之前。收敛循环内 `select_modules_convergent` 的补问（`selection.questions`）同样过一遍视觉问答（同一供给回调，同一判定）。
- **判定（纯函数，机械启发，宁漏判不误判）**：`selection.py` 新增 `vision_answerable(question, problem_text) -> bool`——题面文本中该问题提到的图号（如「图1」）被题面引用过（问题含「图N」且题面也含「图N」，或题面含 `[图N 标注`）**且**问题含尺寸/位置类关键词（尺寸、宽度、长度、走廊、门口、位置、走向、标注、距离、坐标、多大、多少、面积、高度）才尝试；不满足 = 漏判（照旧问用户）。关键词表常量单源。
- **视觉问答供给回调**：`run_recommendation` 新增参数 `vision_qa: Callable[[str], str | None] | None = None`（question 文本 → 答案或 None）。selection 保持纯域，不 import vision；webapp 路由注入实现，未注入 = 无此能力，行为与现状逐字节一致。
- **视觉问答实现**（新模块 `vision_qa.py`，薄传输层，照 vision.py 先例）：输入 = 条目 PDF 路径 + 题面文本 + question。`extraction.locate_topic_pages(pdf, problem_text)` 定位页范围 → `_render_page_png`（复用）逐页渲染 → `describe_image_cached(png, "image/png", prompt=question)`（问题即 prompt）→ 回答含否定词（「没有」「未找到」「图上无」「无法」）判定为无 → 返回 None；多页答案拼接。网络/渲染异常 → VisionError 捕获 → None。
- **缓存键升级**：`vision.describe_image_cached` 缓存键由 `sha256(image)` 改为 `sha256(image + prompt)`——进程内缓存、无落盘兼容负担；现有调用方（图注、上传图片）同图同 prompt 行为不变。按需问答「同图同问题」跨轮次命中。
- **TopicContext 扩展**：`generator.TopicContext` 新增字段 `figure_pdf: Path | None = None`（key 非空且条目带 original_pdf 时由 `resolve_topic_context` 装配点带出条目目录 + original_pdf 解析出的路径；no-topic 形 = None）。默认 None = 旧调用方零改动。
- **答案喂回**：视觉答案构造为澄清问答 `(question, answer)` 并入 clarifications（与用户回答同构，题面后独立段，不污染逐句对照）。已被视觉消化的问题不再进 `question` 事件。
- **缓存兼容**：recommend_cache 不改——视觉答案随 clarifications 进入 `clarify_sha256` 参数指纹（复用警告路径，非阻断），符合既有语义。
- **进度提示**：视觉问答期间 `emit.progress` 发一条「已自动看图回答 N 条问题」提示（可选，不改变终态协议）。

## 测试决策

- 好测试 = 只测外部行为：判定函数纯函数直测；run_recommendation 以注入的假 `vision_qa` 回调验证「答掉 / 部分答掉 / 全答不上 / 未注入」四路径的 question 事件与 clarifications 内容；vision_qa 模块以注入假 transport（照 vision.py 先例）验证「渲染 → 调用 → 否定词判 None」；缓存键升级用 `clear_describe_cache` 前后同图异 prompt 双调用验证两次独立请求。
- 测试模块：`tests/test_selection_vision_qa.py`（判定 + 编排四路径）、`tests/test_vision_qa.py`（传输层）、vision 缓存键测试并入既有 vision 测试文件。
- 既有先例：selection 编排测试（假 LLM 注入）、vision.py 假 transport 测试、topic_library 图注测试。
- 真机验收（工单 03）：2021F 真实调用，走推荐确认「走廊宽度」类问题被自动消化。

## 范围外

- 不改 `enrich_topic_image_notes` 幂等逻辑与存量图注（2021F 图注质量问题由本特性在推荐阶段兜底，不回填）。
- 不改 `RENDER_DESCRIBE_PROMPT`（B 选项，被用户放弃）。
- 不动 recommend_cache 指纹协议。
- 不覆盖「深化 / 修订」阶段的视觉问答（本 spec 只做推荐澄清；接口留了供给回调，后续可复用）。
- 不做落盘缓存（视觉答案缓存维持进程内）。

## 补充说明

- 触发场景 2021F 已核实：图1 信息其实够（走廊宽 30cm、房间 60cm、进深 40cm、门口区域 5cm），视觉模型针对性问答比开放式描述可靠（开放描述曾幻觉「甲乙丙丁」）。
- 判定关键词表放在 selection.py 常量，结构测试防回退（照 library.py BANNED_TOPIC_WORDS 先例可补一条常量存在性断言）。
- git 提交信息 / 工单 / spec 一律中文（仓库硬性约定）。
