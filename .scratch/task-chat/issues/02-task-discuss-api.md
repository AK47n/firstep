# 工单 02：任务商量协议（discuss_task）+ /api/tasks/discuss 端点

**要做什么：**LLM 协议 `discuss_task`（任务顾问角色：用户发表想法/纠正 → AI 回应可行性 + 对实现的影响 + 修正建议）+ 同步端点 + 事件词表 + 测试。

**被谁阻塞：**无（与本文件同级工单 01 无代码依赖；dialog_note 由 01 提供，本工单只产出 reply 文本）。

**状态：** resolved（双轴评审通过 + 整改）

## 验收标准

- [x] events.py 登记 `EVENT_TASK_DISCUSS = "task_discuss"`（词表单源；同步端点不发射 progress 事件，与 buy-discuss 同款）。
- [x] llm.py 新 dataclass `TaskDiscussion`（frozen，`reply: str`）。
- [x] LLM 协议方法 `discuss_task(task, problem_text, qa_text, requirements, module_interfaces, main_c, history) -> TaskDiscussion`（history = [(role, content), ...] 旧→新）；DeepSeek 实现（_retry_parse json_mode，reply 空 → LLMError 重试）；RoutingLLM remote 转发（不进 LOCAL_LLM_METHODS）。
- [x] 系统提示词（中文，任务顾问非执行者：先判用户想法可行性，再说明对任务实现的影响，最后给修正建议；不得替用户直接改 main.c）；user prompt 段拼装：任务描述 + 题面（_truncate_content）+ Q&A（_fit_fulltext_wire，空则无段）+ 需求行（_requirement_lines）+ 模块接口 + 当前 main.c + 对话历史（复用 `_discuss_history_segment` 字符帽先例）+用户最新消息。
- [x] 新端点 `POST /api/tasks/discuss`（同步，webapp.py 任务端点区）：`{output_dir, task_id, history}`；校验：history 非空数组/条目非对象/role 词表外/content 非字符串 → TaskError 400；输出目录不存在/未拆解/任务不存在 → TaskError 400；`_load_revision_context` 读题面/Q&A/需求/接口（platform/slugs 装配照 /api/tasks/execute 先例，main_c 现读）；requirements 缺省 → 空序列（不 400，讨论是沟通不是执行）；LLMError → 502；telemetry 照常（collector → try/finally `recent_llm_workflows.add_completed`）。
- [x] fakes.py：FakeLLM/RecordingLLM 加 `discuss_task`（discussion 参数 + calls 记录，照 discuss_buy_options 先例）；test_llm.py 更新 `PROTOCOL_METHOD_NAMES`。
- [x] 测试：test_llm.py（协议解析/reply 空抛/prompt 段快照/remote 路由）；test_task_progress.py（200/400 各形态/502）。
- [x] 全量 pytest + mypy 改动文件 0 错；中文 commit。

## 评审记录

双轴 code-review（git diff cd00038...94425fd）：Standards 0 硬违规；Spec c3 → **已整改：去掉 message 独立参数，单通道 = history（最后一条 user = 本轮消息，prompt 以 history[-1] 为「你的最新消息」，与 /api/buy/discuss 同款）**——避免双通道下非前端客户端分离 message 与 history 时最新消息错位；前端 push 后发全量历史，评审「讨论历史段与最新消息段重复」判定接受（与 buy-discuss 既有模式一致，强调最新消息对 LLM 无害）。Spec b1（缺题面/main.c 空 400 防御分支）判定接受保留（docstring 注明；与 /api/tasks/execute 同款防御）。判断项：薄壳装配重（与 tasks_execute 端点同形状，接受）、Data Clumps 五元组（execute/run_task 先例惯例，接受）、role 分支三处（校验/渲染/记录语义各不同，接受）。
