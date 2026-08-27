# 工单 02：反馈执行链路（feedback 参数 + 已验证重开 + 状态回填）

**要做什么：**
- `llm.py`：`LLM.execute_task(main_c, task, note, module_interfaces, problem_text, qa_text, feedback="")` 协议签名加可选 `feedback`；`TASK_EXECUTE_SYSTEM_PROMPT` 加「若提供上板实测反馈，按反馈修复实现，只改相关部分，不重写无关代码」；`_task_execute_user_prompt` 新增独立「上板实测反馈」段（在 note 段之后；feedback 为空则整段不出现——对既有测试逐字节兼容）。DeepSeek/RoutingLLM 透传。
- `task_progress.py`：`run_task(..., feedback="")`——feedback 非空时：若任务当前为终态（verified/unverified/failed），先自动 apply_task_status 到 pending（verified→pending 已合法），再执行；执行后迭代记录 kind="feedback"、feedback=文本；状态回填照旧按 verify 类型（compile→绿即 verified / manual→绿则 unverified）。
- `webapp.py`：`POST /api/tasks/execute` 请求加可选 `feedback`（缺省/空串=不反馈；strip 后非空→透传 run_task）。
- `fakes.py`：FakeLLM/RecordingLLM execute_task 支持 feedback 参数并记录。

**被谁阻塞：** 工单 01

**状态：** resolved（双轴评审通过 + 整改：Spec (c) 反馈轮 LLM 失败恢复为反馈前终态而非 pending——previous_status 捕获移到自动重开前；补 test_run_task_feedback_empty_result_reverts_terminal 与任务不存在→error 事件用例。注：feedback 校验与 rollback 验收用例按既有惯例落在 tests/test_task_progress.py（该文件承载全部任务端点测试），不在 test_webapp.py——判定接受）

## 验收标准

- [x] tests/test_llm.py：feedback 透传 + prompt 快照（feedback 段在 note 后；空 feedback 无该段）
- [x] tests/test_task_progress.py：反馈执行（已验证任务自动重开、终态任务反馈 kind=feedback、manual 类反馈后 unverified / compile 类反馈绿后 verified）+ 失败恢复终态回归
- [x] tests/test_task_progress.py：execute 端点 feedback 校验（非字符串→400）+ 任务不存在→SSE error 事件（原计划 test_webapp.py，按文件既有组织落此，见状态行注）
- [x] 既有 execute/e2e 断言无回归（feedback 缺省行为逐字节不变）
