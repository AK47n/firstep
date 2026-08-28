# 工单 01：任务资源 + 自检清单后端（task-insight/01）

Status: resolved

## 目标

Task.resources / TaskIteration.checklist / StepReport.checklist 三字段全链路：
prompt 契约 + 域判决解析 + 落盘 + 报告返回三元组。

## 交付

- `task_progress.py`：Task.resources: tuple[str, ...] = ()（to_dict/
  from_dict/build_task_plan/update_task_fields/insert_task_from_idea/
  set_tasks_needs_redo/_with_task_status 六处同步，解析宽松：非数组 → ()，
  str 项 strip 后保留非空）；TaskIteration.checklist: tuple[str, ...] = ()
  + to_dict + _parse_iterations（新 helper _iter_opt_str_list）；_report_task_step
  返回三元组 (what_changed, user_action, checklist)（llm.report_task_step →
  report.checklist）；run_task 构造 iteration 带 checklist；run_direct_fix 的
  step_report 加 "checklist"。
- `llm.py`：StepReport.checklist: tuple[str, ...] = ()；TASK_REPORT_SYSTEM_PROMPT
  加第三段（3-6 条上板检查清单，每条一句「应观察到什么；若不正常检查哪里」，
  纯软件步 = []；JSON 契约加 "checklist": ["..."]）；report_task_step parse
  解析 checklist（非 list → ()；元素非 str 过滤 strip 去空）；TASK_PLAN_SYSTEM_PROMPT
  加规则 ⑧ resources（互斥资源数组——引脚/外设/中断真实名称，与其它任务共用
  也列出；无新增占用 = []）+ JSON 契约加 "resources": ["PA0"]。
- `tests/fakes.py`：FakeLLM.step_report 参数加 checklist（默认 ("烧录后应看到
  LED 每秒闪烁一次。", "若不闪检查 PA0 与 LED DIO 接线。")）+ RecordingLLM
  同步；FakeLLM plan_tasks 产物（若 fake 直接构造 TaskPlan——检查现有 fake
  形状，resources 缺省即可）。
- `tests/test_task_progress.py`：Task.resources/checklist roundtrip + 旧记录
  缺字段缺省空；build_task_plan resources 宽松（非数组→()、坏项过滤、正常
  保留）；run_task 轮次 checklist 落盘（Fake step 报告带 checklist →
  迭代 checklist 断言）；run_direct_fix step_report 带 checklist。
- `tests/test_llm.py`：report_task_step checklist 解析（缺省/非 list/坏项过滤/
  正常）；plan_tasks resources 契约（build_task_plan 宽松）；既有测试
  适配（StepReport 构造处无破坏——checklist 缺省）。
- 双轴评审 + 全量 pytest 绿后提交。

## 验收

1. pytest 全量绿；旧清单文件（无两字段）读回不炸。
2. 无新协议方法（字段扩展零签名变更）。
3. 双轴评审无硬违规。
