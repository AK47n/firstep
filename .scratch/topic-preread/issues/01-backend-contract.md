# 01 — 后端契约与校验落域：preread_topic 全链改名 + 结构化输出

**要做什么：** 生成页步骤 2 的后端从"赛题简介"升级为"赛题预读"：预读题面返回一句话总览 + 决策点提醒列表（每条含影响步骤、提醒文本、题面原文引用），并做机械校验防 AI 幻觉。用户视角 = 点预读按钮后拿到的是结构化提醒数据，前端可分组、可钉卡。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

## Answer

实现完成并通过双轴评审（code-review：Standards 无硬违规；Spec 主体对齐，3 处"残留"均属工单 02/04 已列范围——前端端点断链归 02、fx/llm.js 死键与 topic_title_from_summary 归 04）。评审整改：PreReadReminder→PrereadReminder 词形统一（与 PrereadResult/全库 preread 一致）；_parse_preread→parse_preread 公开（与兄弟 parse_* 一致）；PREREAD_SYSTEM_PROMPT 数字改 f-string 单源（循 MAX_QUESTIONS 先例，新增 PREREAD_STEP_NAMES 单源、PREREAD_STEPS 由键集派生）；test_norm_*→test_normalize_* 测试全名；全量测试绿 2816 passed，mypy 无新增（17 个既存基线错误非本次引入）。

- [x] LLM 方法 `summarize_topic` → `preread_topic`：输出结构化 JSON `{overview: str, reminders: [{steps: [int], text: str, quote: str}]}`；系统提示词重写——只提取"限定/约束/指定"类事实（必须/只能/不得/限定/采用…），功能描述类不输出；每一步骤语义同步说明（3 平台/5 推荐/6 模块清单/7 引脚/8 骨架/11 深化）；quote 必须逐字取自题面原文（短片段）；输出条数建议 ≤ 12。
- [x] 新叶子模块收机械校验（纯函数，webapp 路由薄壳转调）：steps 合法集 {3,5,6,7,8,11} 或空（空 = 通用限定）、重复合并；text 非空且 ≤ 200 字；quote 非空且 ≤ 120 字、空白归一后必须是题面子串（不命中 → 丢弃 quote 保留 text）；reminders 条数上限 12；overview 非空 ≤ 120 字；返回规范化结果或抛错（中文文案）。
- [x] JSON 解析走既有重试/解析机制；解析或校验失败 → LLMError 大声失败（中文错误、可重试），不经静默降级。
- [x] `LOCAL_LLM_METHODS` 成员 `summarize_topic` → `preread_topic`（本地模型继续可承担，机械校验兜底）；设置页"三个纯文本摘要"文案暂不动（归工单 04）。
- [x] 路由改名：`/api/topic/summarize` → `/api/topic/preread`，请求体 `problem_text`，返回 `{overview, reminders}`；错误映射沿用（400 缺参 / 502 LLM 失败 / 校验失败 502 中文）。
- [x] 删除旧的纯文本 `summarize_topic`（含旧 TOPIC_SUMMARY_SYSTEM_PROMPT），仅保留总览语义进 overview。
- [x] 测试更新齐：FakeLLM（fakes.py 记录型假件 + 远程假件）、test_llm.py（新契约解析/重试/截断/引用校验）、test_webapp.py（端点改名、缺参 400、LLM 失败 502、本地路由组落 local）、新叶子模块纯函数单测（枚举/合并/归一子串/超限/空）。
- [x] 全量测试绿 + mypy 干净。
