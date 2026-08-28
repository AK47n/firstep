# 任务洞察：资源占用 + 上板自检清单（task-insight）spec

## 问题陈述

1. **联调冲突暗雷**：任务逐个验证都过，但两个任务可能共用同一引脚 / 定时器 /
   串口（如都用了 PA0、都占 TIM1），**联调才炸**。学生需要一张「谁占用了哪些
   pin/外设」的汇总表，重复项被标出。
2. **上板自检靠散文**：步骤报告的 user_action 是文字「上电后应看到 LED 闪一次…」，
   学生上板时希望有一份**可勾选的结构化检查清单**（烧完看什么 → 正常什么样 →
   异常查哪），照单子测完再点「上板反馈」。

## 目标

- 拆解任务时 AI 给每个任务标注 `resources`（本任务占用的互斥资源：引脚 / 外设 /
  中断，用接口清单里的真实名称）→ 落盘 `.contest_tasks.json`（Task.resources）。
- 任务推进区顶部「资源总览」表：资源 × 使用任务，同一资源被 ≥2 任务占用 →
  黄色「⚠ 注意」标注（重复不一定是错——可能是先后复用，提示学生上板前确认）。
- 步骤报告升级：`StepReport.checklist`（3-6 条上板检查项，每条一句「观察到什么 /
  若不正常查什么」）→ 随轮次落盘 TaskIteration.checklist → 结果面板渲染为
  可勾选清单（勾选态 localStorage 备忘，不落盘、不动状态机）。

## 用户故事

1. 拆解任务后，每张任务卡显示「资源：PA0 · TIM1 · I2C0」小徽标行。
2. 任务推进区顶部（进度总览下方）出现「资源总览」表：每行 = 一个资源 + 用到
   它的任务（卡号+标题）；被 2+ 任务共用的资源行标黄「⚠ 多任务使用」。
3. 上板前我打开某步的结果面板，看到「上板自检清单」：□烧录后应看到 LED 每秒
  闪一次 □若不闪检查 PA0 与 LED DIO 接线 □确认后点「上板反馈」——逐条勾选，
   刷新页面勾选仍在（localStorage）。
4. 旧清单（无 resources）/ 旧轮次（无 checklist）读回不炸，字段缺省为空。

## 实现决策

- **Task.resources: tuple[str, ...] = ()**（to_dict / from_dict / build_task_plan /
  update_task_fields / insert_task_from_idea / set_tasks_needs_redo /
  _with_task_status 六处同步）。解析宽松（辅助信息宁空勿拒）：非数组 → ()；
  数组内非 str / 空串项过滤。
- **TASK_PLAN_SYSTEM_PROMPT** 加规则 ⑧：`resources = 本任务将占用的互斥资源
  数组（引脚如 "PA0"、外设如 "TIM1"/"UART0"、中断如 "TIM1_IRQn"——只用模块
  接口清单里出现的真实名称，本任务不新增占用 = []；与其它任务共用的资源也要
  列出（供后续总览发现重复））+ JSON 契约字段 `"resources": ["PA0"]`。
- **TaskIteration.checklist: tuple[str, ...] = ()**（to_dict / _parse_iterations
  用新 helper `_iter_opt_str_list`）。
- **StepReport.checklist: tuple[str, ...] = ()** + **TASK_REPORT_SYSTEM_PROMPT**
  加第三段：「checklist = 上板/验证检查清单（3-6 条，每条一句"应观察到什么；
  若不正常检查哪里"，原子可勾选；纯软件步无物理动作 = []）」+ JSON 契约
  `"checklist": ["..."]`；llm 解析：非 list → ()；元素非 str 过滤。
- `_report_task_step` 返回三元组 (what_changed, user_action, checklist)；
  run_task 构造 iteration 带 checklist；run_direct_fix 的 step_report 带 checklist。
- **资源总览纯前端**：`fx/task.js` 新 `resourcesOverviewHTML(plan)`——从
  plan.tasks[].resources 聚合（资源名 → 任务列表），同一资源 ≥2 任务 →
  `.res-conflict` 行标黄「⚠ 多任务使用，上板前确认」；空 = ""（不渲染）。
  零后端端点。
- 任务卡资源徽标：`taskResourcesHTML(task)`（「资源：」+ chips）。
- 自检清单渲染：`taskChecklistHTML(iteration, key)`——checkbox 列表，勾选态
  localStorage `firstep.checklist.v1.<key>`（key = taskId+"/"+seq），onchange
  写盘；**纯备忘，不影响状态机**（声明在 UI 文案）。结果面板在步骤报告块后
  渲染最新轮 checklist（key = task.id + "/" + iteration.seq；反馈轮 = 新 seq）。
- 卡片与总览集成：taskCardHTML 卡描述后插 taskResourcesHTML（非空才渲染）；
  tasksGridHTML 资源总览由 ui/generate-tasks.js 在 tasksRender 里渲染到
  #tasks-resources 容器（紧跟 #tasks-overview 后，空串隐藏）。

## 测试决策

- `tests/test_task_progress.py`：Task.resources / TaskIteration.checklist 的
  roundtrip + 旧记录缺字段缺省空；build_task_plan 宽松解析（非数组 → ()、坏项
  过滤）；run_task 轮次 checklist 落盘（Fake 步骤报告带 checklist）；run_direct_fix
  step_report 带 checklist。
- `tests/test_llm.py`：report_task_step checklist 解析（缺省 () / 非 list () /
  坏项过滤 / 完成）；plan_tasks 契约测（resources 宽松）；PROTOCOL 与方法清单不变
  （无新协议方法——checklist 是既有 report_task_step 的字段扩展）。
- `tests/fakes.py`：FakeLLM.step_report 参数加 checklist（默认 2 条中文
  checklist）+ RecordingLLM 同步。
- JS：task.test.mjs（taskResourcesHTML 渲染/空 / resourcesOverviewHTML 聚合与
  冲突标黄 / taskChecklistHTML 勾选与 localStorage 读写——jsdom 桩 / 卡集成）；
  fx-guard 登记 3 新导出。
- 全量 pytest + JS + 语言检查；双轴评审逐工单。

## 范围外

- 资源冲突自动修（只标黄提示）。
- resources 的冲突语义分级（独占/共享/复用兼容）——本期「≥2 任务 = 提示」。
- checklist 勾选态落盘 .contest_tasks.json（只做 localStorage 备忘）。
- task_chat/商量与资源/清单联动。
