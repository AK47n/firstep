# 工单 01：select 输出上限 + 超长守卫 + 响应留痕（llm.py 单文件切片）

Status: claimed
Depends: 无
Blocks: 无

## 目标

修 deepseek-v4-flash 模块推荐输出失控（20K tokens/次、parse 失败、重试烧钱烧时间）：
请求带 max_tokens 上限、输出超长免重试、响应脱敏摘要进观测。

## 改动点（全在 src/contest_generator/llm.py + tests/）

1. 常量 `SELECT_MAX_OUTPUT_TOKENS = 4096`（select 输出上限）。
2. `_chat_once(..., max_tokens: int | None = None)`：payload 加 `max_tokens`（None 不加）。
3. `_retry_parse(..., max_tokens: int | None = None)`：透传 `_chat_once`。
4. `select_modules`：`_retry_parse(..., max_tokens=SELECT_MAX_OUTPUT_TOKENS)`；parse 闭包开头加超长守卫
   `if len(content) > 60000: raise LLMError("模块选择输出异常超长（{n} 字符）：疑似模型输出退化/循环，放弃重试", kind=ERROR_KIND_CLIENT)`
   （_retry_parse 对 client 错误 break 不重试——llm.py:1375 既有分支，零改动）。
5. 观测留痕：`LLMCallObservation.content_excerpt: str | None = None`（前 120 字符、换行压平、超长加省略号）；
   `collect`/`_observe_call` 加 `content_excerpt` 参数（缺省 None）；`_observe_chat_result` 从 result.content 提取；
   `to_log_extra` 带出。脱敏：只留前缀，不含完整响应。
6. SELECT_SYSTEM_PROMPT 末尾加紧凑输出要求（每条需求描述 ≤ 40 字、reason ≤ 20 字、不重复题面原文）。

## 测试（tdd 先红）

- test_llm.py：
  - select_modules payload 含 `max_tokens == 4096`（transport.calls 断言）；其他调用（如 summarize_topic/clarify）payload 不含 max_tokens。
  - 超长输出：FakeTransport body = 60001+ 字符合法 JSON → LLMError kind=client，calls 长度 == 1（不重试）。
  - 正常 SELECTION_JSON 响应：观测 collector 断言 content_excerpt == 响应前 120 字符（压平后）。
  - 失败响应（畸形 JSON）：观测 content_excerpt 仍记录。
- 既有测试全绿（payload 键集合无精确断言，加键不破坏；确认 test_llm.py:418-419 只断言 model/response_format）。

## 验收

- 全量 pytest 绿 + mypy 干净。
- 重启服务后：select 请求带 max_tokens；再遇输出失控，单次 ≤ ~60s、至多 1 次尝试即报错，观测带 content_excerpt。

## 实施记录

- llm.py：新增常量 SELECT_MAX_OUTPUT_TOKENS=4096 / SELECT_MAX_OUTPUT_CHARS=60000 / CONTENT_EXCERPT_CHARS=120；
  `_chat_once`/`_retry_parse` 加 `max_tokens: int | None = None` 透传（None=不带字段，其余调用零回归）；
  select_modules 传 max_tokens=4096，parse 闭包加超长守卫（>60000 字符 → LLMError kind=client，
  _retry_parse 对 client break 免重试——复用既有分支 llm.py:1375）；
  观测加 content_excerpt（`_content_excerpt`：换行压平 + 前 120 字符 + 省略号，脱敏前缀；
  LLMCallObservation/collect/_observe_call/_observe_chat_result/to_log_extra 全链路透传）；
  SELECT_SYSTEM_PROMPT 末尾加紧凑输出要求（需求描述 ≤40 字、reason ≤20 字、不重复题面）。
- tests/test_llm.py：+6 测试（payload max_tokens 断言 / 非 select 调用无 max_tokens / 超长只 1 次尝试
  kind=client / 成功与解析失败观测 content_excerpt / 压平截断）。
- 教训：测试构造多行 JSON 时，换行必须放 token 间（字符串值内裸换行非法）；_api_response 双层
  json.dumps 会把 \uXXXX 转义序列再次转义（loads 后仍是字面 6 字符而非换行）。
- 全量 2172 通过（原 2166 + 6）、mypy 59 文件干净；服务已重启（新 PID 22876）生效。

## 评审记录

- Spec 轴（subagent 12d94cff）：5 条验收全通过 + 范围外遵守，无阻塞。实证：payload 条件加 max_tokens
  （llm.py:2113-2115），grep 全文件仅 select_modules 传值（llm.py:1233→1380→1403）；超长守卫 kind=client
  且 _retry_parse 对 client break（llm.py:1421-1424）；content_excerpt 成功与 parse 失败两路都记
  （llm.py:1407-1417 / 2033-2054）；_ChatResult 仅 status==200 构造（llm.py:2265），非 200 走
  _observe_call 直调 excerpt=None，body 不泄入；实测 -k 13 passed、全量 2172 passed、mypy 干净。
  非阻塞建议：非 select 无 max_tokens 测试可参数化补 clarify；截断型 parse 失败仍走默认 parse 重试
  （≤5 次）符合 spec 快速失败设计，双保险自洽。
- Standards 轴：subagent 长时间未返回被中断；自查覆盖——docstring/注释中文、常量集中与周边一致、
  错误文案可操作、脱敏契约（excerpt 只 120 字符前缀）、测试命名与断言风格一致，无违规项。

Status: resolved
