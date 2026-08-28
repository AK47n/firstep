# 灵活修正（idea-fix）

## 问题陈述

任务推进（逐步深化）的所有入口都**绑定单张任务卡**：「做这一步」「和 AI 商量（该卡）」「上板反馈」「烧录到板子」「回到这轮之前」。但实际使用中大量问题**不属于任何一张卡**：

- 用户突然看到 main.c 某处不对劲（阈值、引脚、状态机条件），想立刻改；
- 用户突然想到一个改进点（「进弯道前先减速」），想告诉 AI 并让它改；
- 用户有想法但不确定要不要改、怎么改，想先跟 AI 聊。

现状没有入口：硬塞给某张卡的商量（语义错位）、或点「重新拆解」（整清单覆盖，太重）。用户原话（语音转文字）：「缺一个灵活的修正的地方……突然就出来这个问题或者说是我突然想到有什么需要改进的点，我想要告诉然后再帮我改」。

## 目标

在任务推进区加一个**全局「新想法 / 问题」入口**（不绑定任务卡）：

1. 用户随时输入一个想法/问题；
2. AI 分析并分类：`new_task`（新功能需求）/ `direct_fix`（改现有代码）/ `discussion`（先讨论）；
3. 三类都提供「落地按钮」：
   - `new_task` → 生成任务卡插入清单（自动算依赖与顺序、标注评分点）；
   - `direct_fix` → 生成改动预览（确定性 diff）→ 用户确认 → 备份 → 写盘 → 编译验证 → 结果展示 → 可回滚；
   - `discussion` → 展示 AI 建议，用户可继续输入，也可一键把建议转成任务/修正（漏斗态，不建独立对话区——独立全局对话区排下一批）；
4. **联动**：直接修正落地后，AI 给出的受影响任务（`affected_task_ids`）自动标 `needs_redo`（「⚠ 建议重做」徽章 + 一键重做），保证修正不游离于清单账目之外；
5. 修正/新任务都落盘（.contest_tasks.json），刷新不丢；修正可回滚（复用备份机制）。

## 用户故事（验收口径）

1. 我在任务推进区顶部随时能看到「💡 新想法 / 发现的问题」输入区，不绑定任务卡。
2. 提交想法后看到 AI 的分析卡：分类徽章（新功能 / 改代码 / 讨论）+ 一句话理解 + 落地按钮。
3. 点「生成任务」→ 任务卡插入清单，`depends_on` / 顺序 / `score_refs` 由 AI 给出、落盘 `needs_redo=false` 新任务；清单刷新可见。
4. 点「改动预览」→ 显示确定性 diff（复用效果 diff 渲染）→ 确认后执行：备份 → 写盘 → 编译验证（绿 = 已验证 / 无工具链 = 未验证 / 修一轮仍红 = failed）→ 结果面板可回滚（复用 /api/revise/rollback）。
5. 修正结束后，`affected_task_ids` 里存在的任务卡出现「⚠ 建议重做」徽章 + 「重做此步」按钮（= 重置为 pending 并清除 needs_redo），重做后走既有单任务执行闭环。
6. 输入的想法文本与最终落地结果在结果区保留展示（会话内），落盘以 .contest_tasks.json 为准。
7. 分类为「讨论」时展示 AI 建议，且提供「把建议变成任务 / 变成修正」两个转换按钮（漏斗态）。
8. 旧清单（无 needs_redo 字段）读取兼容 = 默认 false。

## 实现决策

### 后端

- **llm.py**：
  - `IdeaAnalysis @dataclass(frozen)`：`kind: str`（new_task|direct_fix|discussion）、`reply: str`、`new_task: Mapping | None`（title/description/score_refs/depends_on/verify）、`fix_summary: str`、`affected_task_ids: tuple[str, ...]`（两类修正都填，可空）。
  - `Protocol.analyze_idea(idea, problem_text, qa_text, requirements, score_points, module_interfaces, main_c, plan)` → `IdeaAnalysis`（json_mode；`kind` 非法 / `reply` 缺失 → LLMError 重试；`new_task` 仅 new_task 非空；affected_task_ids 缺省空元组）。
  - `Protocol.apply_idea_fix(idea, fix_summary, affected, module_interfaces, problem_text, qa_text, main_c)` → `str`（新 main.c 全文；只按想法改，其余原样保留）；文本模式，复用 execute_task 的 _retry_parse 形状。
  - `TASK_IDEA_SYSTEM_PROMPT` + `_idea_user_prompt`（想法 + 清单状态摘要（id/标题/状态/依赖）+ 题面/Q&A/需求/评分点/接口/现有 main.c，各段 _truncate_content）。
  - `IDEAFIX_SYSTEM_PROMPT`（或并入 TASK_IDEA_SYSTEM_PROMPT 的 apply 分支；实现时定）+ `_idea_fix_user_prompt`。
  - RoutingLLM：analyze_idea / apply_idea_fix 走 remote（passthrough，不进本地方法集）。
- **task_progress.py**：
  - `Task` 加 `needs_redo: bool = False`（to_dict 全字段；parse 用缺省读回，旧清单兼容）。
  - `insert_task_from_idea(plan, new_task)`：纯函数 → 计算插入位置（简单策略：放在依赖链末端——其 depends_on 全部完成/存在之后、首个无依赖待做之前；实现时允许简化为 append + 顺序号重排），返回新 plan。
  - `mark_tasks_needs_redo(plan, ids)`：纯函数 → 对应 task.needs_redo = True；落盘由 webapp/helper 做（沿用 _with_task_status 模式或新 _with_plan）。
  - `run_direct_fix(...)`：新管线（形状对齐 run_task 的非任务部分）：备份（backup_tree / revise_backup_root）→ llm.apply_idea_fix → 写盘 → main_diff → verify_compile_tail(subject="修正结果") → 返回 `{status, backup_id, compile, main_diff, message}`；**不造 TaskIteration**（游离于任务轮次，回滚走 backup）；LLM 空结果 → TaskError；异常不覆盖已写盘成功的结果。
- **events.py**：新增 `EVENT_IDEA_ANALYZING = "idea_analyzing"`（SSE 序列 idea_analyzing → idea_result → done）；direct_fix 执行复用 compile_start / fix_start / verify_result / task_reporting 事件词表（不新增）。
- **webapp.py**：
  - `POST /api/tasks/idea/analyze`（SSE：idea_analyzing → idea_result{done}：{task, ...} 载荷 = IdeaAnalysis.to_dict；`data` 负载带 `analysis`）——输入 {output_dir, idea}。
  - `POST /api/tasks/idea/insert`（同步）：{output_dir, new_task} → 插入 + 落盘（.bak 前置备份）→ 返回 {plan}。
  - `POST /api/tasks/idea/fix`（SSE，复用执行事件词表 + backup/compile/main_diff/done 载荷）：{output_dir, idea, fix_summary, affected_task_ids} → run_direct_fix + 落盘 affected needs_redo → done 载荷含 {status, backup_id, compile, main_diff, message, affected}。
  - `POST /api/tasks/idea/mark-redo`（同步）：{output_dir, task_ids} → 落盘 needs_redo。
  - 错误分级沿用（无清单/目录 → 400 中文）。
- **tests/fakes.py**：FakeLLM / RecordingLLM 加 analyze_idea / apply_idea_fix（固定返回 + calls 记录）。

### 前端

- **fx/task.js**：
  - `ideaResultHTML(analysis)`：分析卡（分类徽章 + reply + 按 kind 渲染落地按钮区；discussion = 建议 + 两个转换按钮）。
  - `taskNeedsRedoBadge(task)` + taskCardHTML 集成：`needs_redo` 真 → 卡头「⚠ 建议重做」徽章 + 操作行加「重做此步」（= update status pending + 清 needs_redo，复用 tasksSetStatus 通道或新接口）。
  - 新导出登记 fx-guard。
- **ui/generate-tasks.js**：
  - tasks-box 顶部渲染 idea 输入区（textarea + 「分析这个想法」按钮 + busy 守卫 + 结果容器）；复用跨簇重置时机（revise-context-loaded / tasks-invalidated 清空）。
  - `tasksIdeaAnalyze`（SSE idea_analyzing→idea_result）→ 渲染 ideaResultHTML；按钮委托：`生成任务`（POST insert → tasksRender）／`改动预览并执行`（IDEAFIX SSE：task_reporting 等事件文案复用；done → tasksRender + 结果面板嵌套 mainDiffHTML + 备份回滚按钮）／`把建议变成任务/修正`（同前两按钮，直接调同一后端）。
  - affected 标记后刷 tasksGridHTML（needs_redo 徽章出现）。
- **index.html**：idea 输入区行 + `.idea-*` CSS（accent 风格，与任务区一致）+ `.task-redo-badge`（warn 色）。
- **tests/js**：fx/task.js 新函数渲染断言（三种 kind / needs_redo 徽章 / 按钮显隐 / 转义）；fx-guard 登记。

### 测试决策

- pytest：llm（analyze_idea 解析/重试/prompt 段/routing；apply_idea_fix）+ task_progress（insert_task_from_idea 位置与落盘 / mark_tasks_needs_redo / run_direct_fix 管线与降级 / needs_redo roundtrip 与旧清单默认 false）+ webapp（三路由 + SSE 事件序列 + 400 分级）+ fakes。
- JS：fx/task.js 渲染 + 桥；全量 node --test；fx-guard。
- 探针：真实页面输入区 → 分析（短想法）→ 渲染；不强行执行 LLM 改动（成本控制），执行路径以 pytest FakeLLM 覆盖 + 手动实机验证。

## 范围外（下一批）

- 独立「全局工程级商量」对话区（本批 discussion = 漏斗态）；
- 清单微编辑（改描述/依赖）与拖拽调序；
- 想法草稿箱/批量处理；
- 自动连做 / 自动修正。
