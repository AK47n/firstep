# 01 — 拆解任务清单

**要做什么：** 学生生成（或修订）工程后，点一次「拆解任务」→ 工具调 LLM 把题面 + 功能需求 + 评分点 + 模块接口 + 当前 main.c 拆成有序任务清单 → 落盘 `.contest_tasks.json` → 前端展示任务卡只读网格（标题 / 描述 / 关联分值点 / 前置任务 / 状态徽章 / 验收方式标注）。重新拆解可覆盖旧清单（旧清单备档 `.contest_tasks.json.bak`）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**评审记录**（code-review 双轴，HEAD=1468730）：Standards 2 条硬伤已修 —— ① `_task_plan_user_prompt` 硬编码接口引导语绕开 `SKELETON_INTERFACES_HEADING` 单源 → 改用常量；② 功能需求编号行在 deepen/task-plan 两处复制 → 抽 `_requirement_lines` 共用（impact 变体带 `- ` 前缀且属既有代码，未并入）。Spec 3 条已修 —— ① `generated_at` 从未落定（done 载荷与落盘均为空）→ 域层落定时间戳，测试断言；② `score_refs` 无已知集时未置空（spec「无评分表时为空」）→ 置空 + 测试更新；③ 事件总线注释与实现不符（"零耦合"谎称）→ 注释修正。判定性条目保留：RaisingLLM 缺 plan_tasks 非问题（结构性协议，无枚举断言）；6 参数据团随 LLM 协议先例（deepen_main_c 亦多参）。

**验收：** 全部 ✓（清单见上方 checklist，测试 test_task_progress.py 17 条 + 全量 2515 通过；mypy 0 错；JS 484 通过）。

- [x] 任务域：`Task` / `TaskPlan` 模型 + 状态与验收词表（pending / doing / verified / unverified / failed / skipped；verify = compile / manual）+ `parse_task_plan`（LLM 原始 dict → 模型；畸形输出照 `parse_score_points` 先例：字段缺失 / 类型错 → 拒收或修正，空任务清单 → TaskError）
- [x] LLM 协议新增 `plan_tasks(...)`（DeepSeek 实现 + RoutingLLM 转发 + 测试假 LLM 扩展；`_retry_parse` 兜底复用）
- [x] `.contest_tasks.json` 读写 + 形状校验（缺文件 = 未拆解；坏 JSON = TaskError → 400 中文；版本字段向后兼容），落盘与生成产物零交叉
- [x] `POST /api/tasks/plan`（SSE）：`{output_dir}`（可带 problem_text 覆盖，照 /api/revise/deepen 先例）；事件 `task_planning`（events.py 词表新增）→ done（`{tasks, generated_at}`）；缺上下文（无题面 / 无需求清单）→ 400 中文提示（照 /api/revise/context 判断口径）；`force` 重拆：旧清单改名 `.bak` 备档再覆盖
- [x] 前端：卡 11「修订与深化」内新增「任务推进」子区 + 「拆解任务」按钮（含重新拆解入口）+ 任务卡只读网格渲染（状态徽章 / 分值点 / 前置依赖 / verify 标注），纯函数入 fx、UI 簇按迁移规则
- [x] `TaskError` 登记 errors.py 错误映射表（400 中文）
- [x] 测试：parse 合法/畸形；落盘 roundtrip + 坏 JSON；SSE 事件序列；假 LLM 全链路（照 test_deepen.py / test_selection.py 先例）


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
