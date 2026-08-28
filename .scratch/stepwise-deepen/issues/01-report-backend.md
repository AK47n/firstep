# 01 — 后端：步骤报告 LLM 操作 + 轮次字段 + 进度事件（全链路后端）

**要做什么：** 每步任务执行并编译验证完成后，AI 额外产出「我做了什么 + 接下来你要做什么（含接线/上板指引）」两步报告，随任务轮次落盘并通过执行流返回——后端全链路打通（LLM 调用 → 数据模型 → SSE 载荷），前端暂只透传不渲染。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] LLM 协议新增报告操作 `report_task_step`：入参 = 任务（标题/描述/验收方式/采纳的对话结论）+ 编译验证结果 + 代码 diff 摘要 + 模块接口清单；输出 JSON `{what_changed, user_action}`（均为字符串，可为空）；系统提示与用户提示均为中文，要求接线/上板指引落到具体引脚与模块（引用接口清单里的宏/引脚名）。
- [x] 报告解析与既有 discuss_task 同款 json_mode + 容错；RoutingLLM 直通远程（不进本地方法集）；FakeLLM / RecordingLLM 同步实现。
- [x] 任务轮次记录（TaskIteration）新增 `what_changed` / `user_action` 两个可选字段（序列化缺省空字符串）；旧清单（无这两个字段）读取兼容。
- [x] 单任务执行管线（run_task）：编译验证之后、轮次构造之前调用报告操作（输入复用已构建的模块接口清单；diff 截断传入）；报告调用任何失败都降级为空串、不阻断任务落盘终态（降级路径有注释说明为什么）。
- [x] 新进度事件 `task_reporting`（报告调用前发射，独立 try 与报告调用分离——发射失败不跳过报告）；`/api/tasks/execute` SSE 事件序列含该事件，done 载荷（task）含两个新字段。
- [x] pytest：报告成功字段落盘 / 报告失败降级为空且任务仍为终态 / 旧轮次数据兼容读取 / SSE 事件序列含 `task_reporting` / 解析容错。

**答复（code-review 双轴评审整改）：**
- Spec 轴：报告 prompt 已并入「用户沟通结论（采纳自对话）」，对应测试断言补上；diff 截断口径 docstring 改为「截断在 prompt 层处理」。
- Standards 轴：`task_reporting` 发射与报告调用分离（各自 try/except，发射失败不跳过报告）；`except Exception` 宽捕获保留——spec 明定「任何失败降级不阻断」（主产物已落盘，报告是附加产出），docstring 已说明。`tuple[str,str]` 返回刻意保留：task_progress 运行时不能 import llm（循环依赖，llm.py imports task_progress.build_task_plan），StepReport 类型仅在 TYPE_CHECKING 可见。
- 前端不渲染 `what_changed`/`user_action`、SSE 缺 `task_reporting` handler——均为工单 02（前端）验收项，非本工单缺口。
- 全量 pytest 2608 passed（含评审整改后复查）。

**提交：** 见 git 历史（工单 01 提交）。
