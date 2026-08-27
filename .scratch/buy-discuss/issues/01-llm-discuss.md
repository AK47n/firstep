# 工单 01：LLM 协议 discuss_buy_options（讨论 + 可行性校核）

> 来源：.scratch/buy-discuss/spec.md §2.2（§五 测试决策）
> 状态：resolved（双轴评审通过 + 整改：Standards 5 项 / Spec 3 项，E2E 10/10）

**要做什么：**
- `llm.py`：LLM 协议加 `discuss_buy_options(...)` → `BuyDiscussion`（reply: str + review: BuyReview | None）：
  - `BuyReview` @dataclass(frozen)：verdict（feasible | risky | infeasible，词表外值修正 feasible）/ reason / suggestion。
  - 参数：problem_text / requirement（需求句）/ platform / solutions（词表方案，format_wordlist_prompt 或行级）/ history（tuple[(role, message), ...]）。
  - DeepSeek 实现：`_retry_parse`（json_mode）+ 用户 prompt（题面截断 + 需求句 + 平台 + 方案清单 + 历史逐条截断 + 输出契约：reply 自由文本 + review 仅在用户最新消息提出自定方案时输出）；JSON 形状非法降级（reply 空 → LLMError/重试；review 缺失 = None）。
  - RoutingLLM 转发 remote（不进 LOCAL_LLM_METHODS，local 不可用于讨论）。
- 单源常量：DISCUSS 系统提示词（立场 = 顾问非裁判 + 校核维度：接口/电压/资源/题面对症 + verdict 三档 + suggestion 可指向词表方案比对）+ 预算（历史条数上限 = 8 轮 + wire 兜底）。
- 事件：EVENT_BUY_DISCUSS 登记 events.py（词表单源）。
- 错误：DiscussionError 或复用 LLMError？（域错误错误映射登记与否——LLMError 由传输侧翻译，确认走既有 `_retry_parse` 语义）。

**被谁阻塞：** 无。

**验收标准：**
- [x] 协议签名 + BuyDiscussion/BuyReview 结构（review 为 None 时序列化不出现）
- [x] DeepSeek 解析：合法 JSON / review 缺失 / verdict 词表外修正 / reply 空 → 重试或 LLMError
- [x] RoutingLLM 转发 remote 且 LOCAL 不可用
- [x] prompt 含题面/需求句/平台/方案清单/历史（截断），快照断言
- [x] tests/test_llm.py 全绿；中文 commit（工单 01）
