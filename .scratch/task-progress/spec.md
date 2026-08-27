# 任务推进（task-progress）— spec

## 问题陈述

当前管线的"生成后"能力只有两个：修订（新 Q&A → 影响分析 → 重生成）与深化（AI 一次填完 main.c 全部 TODO → 编译验证）。学生拿到工程后想把整道题做出来时，面临两个痛点：

- **深化是一口吃胖子**：一次 LLM 调用填完所有 TODO，中间无法纠偏；某一步做坏了，全部结果都要重新来过（只能回滚整树）。
- **题目进度不可见**：题目的完成状态（哪些功能做完了、哪些还没做、哪个分值点差临门一脚）没有载体，学生不知道"做到哪了、下一步做什么"。

用户原话（语音转文字，意为）：生成器已能产出工程，下一步想让工具帮助用户**继续往后生成、直到把这道题做出来**；困惑于交互模式是一轮一轮地问、还是反复生成加提示窗对话。已决：两者都不是——用**任务清单驱动**：AI 把题目拆成有序任务，学生逐卡推进，每步编译验证、可回滚，疑问通过任务上的补充框表达。

## 方案

在生成页「修订与深化」卡内新增**任务推进**子区（与修订并列，共用上下文装配），形成生成后流水线：**拆任务 → 逐任务执行 → 每步编译验证 → 全部做完**。

- **拆任务（按钮手动触发）**：点「拆解任务」→ LLM 读题面（含评分点/功能需求层/Q&A）+ 模块接口清单 + 当前 main.c → 产出任务清单（每任务带标题、描述、关联评分点、前置任务、验收方式）→ 落盘 `.contest_tasks.json`（输出目录，纯新增隐藏文件，照 `.contest_context.json` 先例）。可随时「重新拆解」覆盖（旧清单备档）。
- **任务卡**：每任务一张卡，状态徽章（待做 / 进行中 / 已验证 / 未验证 / 失败 / 已跳过）+ 关联分值标注；卡上有「做这一步」按钮、可留空的**补充框**（向 AI 补一句说明——"提示窗对话"附着在任务上，不是无根聊天）、跳过 / 重做 / 人工改标 / 回滚到本任务执行前。
- **单任务执行**：一次 LLM 调用，输入 = 当前 main.c（服务端现读，手工编辑保留）+ 该任务描述 + 用户补充 + 模块接口清单 + 题面/Q&A/需求清单；输出 = 实现该任务后的 main.c **全文**（与深化同形状，prompt 约束"只实现本任务，其余区域保持原样"）→ 写盘前整树备份（可回滚）→ 编译验证闭环（与深化同款：工具链探测 → 编译 → 失败修一轮 → 重编译；无工具链 = 大声降级）。**逐任务手动点，不做 AI 自动连做。**
- **验收**：编译 passed → 标记「已验证」（可人工改标回「待做」重做）；无工具链 → 「未验证」（结果保留）；修一轮仍红 → 「失败」（保留报错 + 可回滚）。AI 标注 `verify: manual` 的任务（如"上板观察循迹"）即使编译通过初始也为「未验证」，由学生上板后手动标「已验证」（用户拍板）。
- **任务清单落盘**：`.contest_tasks.json` = 任务项（id/title/description/score_refs/depends_on/verify/status）+ 生成时间；状态随执行/改标实时更新。修订执行（模块集变化 → 重生成）后旧任务清单作废：删除该文件，前端提示重新拆解。
- **与深化的关系**：任务推进成为主入口；现有「直接深化」按钮保留（兼容，一次干完）。两者共用同一条「备份 → 写盘 → 编译验证」管线尾段。

## 用户故事

1. 作为参赛学生，我想要生成后点一次「拆解任务」就看到按功能拆好的任务清单（带前置关系与分值点），以便知道这道题分几步、先做什么、哪步最值钱。
2. 作为参赛学生，我想要每个任务单独执行、单独编译验证，以便小步推进，某一步做坏了只回滚那一步，不影响已完成的任务。
3. 作为参赛学生，我想要任务卡上有可留空的补充框，以便执行前向 AI 补一句说明（如"用 10ms 定时器"），而不是重新拆分或盲跑。
4. 作为参赛学生，我想要任务可跳过、可重做、可人工改标（上板确认后标「已验证」），以便上板类任务和现场调整也能走通流程。
5. 作为参赛学生，我想要任务执行前的整树备份与一键回滚，以便改坏时恢复执行前状态。
6. 作为参赛学生，我想要任务清单落盘在输出目录，以便隔天 / 换机器 / 从历史目录入口继续推进，进度不丢。
7. 作为参赛学生，我想要任务状态与分值点透明（哪题功能评分点对应哪个任务、进度如何），以便把握"做到哪了"。
8. 作为参赛学生，我想要任务推进只用编译绿做「已验证」门槛、上板类明确标「未验证」等我自己确认，以便守住"生成即会跑"的承诺不变成虚假承诺。
9. 作为参赛学生，我想要「直接深化」仍可用（一键全做完），以便赶时间时一口吃成胖子。
10. 作为后续会话的 AI，我想要从 `.contest_tasks.json` 恢复任务清单与进度（id / 描述 / 状态 / 备注），以便接续推进不看前端。

## 实现决策

- **新域模块 `task_progress.py`**（照 `deepen.py` 先例，域判决 + 编排 + 错误类型归域）：`Task` / `TaskPlan` 模型、`parse_task_plan`（LLM 原始输出 → 模型，照 `parse_score_points` 先例：畸形输出 → 重试兜底 / 拒收）、任务状态机常量（`pending / doing / verified / unverified / failed / skipped`）、`run_task`（单任务域编排）、`.contest_tasks.json` 读写与形状校验（照 `context_manifest.py` 先例，缺文件 = 未拆解，坏 JSON = 400 中文）、`TaskError` 登记 `errors.py`。
- **LLM 协议新增两个操作**：`plan_tasks(problem_text, qa_text, requirements, score_points, module_interfaces, main_c) -> dict`（任务清单）与 `execute_task(main_c, task, note, module_interfaces, problem_text, qa_text) -> str`（实现后的 main.c 全文）。DeepSeek 实现 + RoutingLLM 转发 + 假 LLM（测试）同步扩展；`_retry_parse` 兜底复用。
- **任务模型**（决策-rich 形状，内联自拍板讨论）：

  ```json
  {"version": 1, "generated_at": "…",
   "tasks": [{"id": "t1", "title": "…", "description": "…",
              "score_refs": ["s1", "s2"], "depends_on": [],
              "verify": "compile", "status": "pending", "note": ""}]}
  ```

  `id` = 序号（`t1..tn`）；`score_refs` = 关联评分点 id（无评分表时为空）；`depends_on` = 前置任务 id（AI 判断，用于展示与排序，不强制阻断）；`verify` ∈ `compile`（编译绿即验证）/ `manual`（需上板人工确认）。
- **`run_task` 管线**：读任务与上下文 → `emit(task_executing)` → LLM `execute_task`（空结果 = TaskError）→ 整树备份（复用 `revision.backup_tree` + `revise_backup_root`，与深化同一回滚入口）→ 写盘 main.c → 确定性 diff（复用 `deepen._main_diff` 或抽公共）→ 编译验证闭环。**先抽公共尾段**（resolve_compile_toolchain → compile → 修一轮 → recompile → 状态判定），`run_deepen` 与 `run_task` 共用，消除重复。
- **API 契约**（照 `/api/revise/*` 先例，路由薄壳 + SSE 流化）：
  - `POST /api/tasks/plan`（SSE）：`{output_dir}`（可带 `problem_text` 覆盖，照 deepen）；事件 `task_planning`（新词表）→ done（`{tasks, generated_at}`）；缺上下文（无题面/无需求清单）→ 400 中文提示（照 `/api/revise/context` 判断口径）。
  - `POST /api/tasks/execute`（SSE）：`{output_dir, task_id, note?}`；事件 `task_executing`（新词表）→ `compile_start` → `fix_start`（仅首轮失败）→ `verify_result` → done（`{task, status, backup_id, compile, main_diff, message}`，形状同 deepen 尾段）；服务端现读 main.c（手工编辑保留）。
  - `POST /api/tasks/status`（同步 JSON）：`{output_dir, task_id, status}` 人工改标（`verified` 改回 `pending` 重做 / `skipped` 跳过 / 非 verified 改 `verified` 上板确认）+ 落盘。
  - `POST /api/tasks/replan`（同步 JSON）：`{output_dir}` 重新拆解（旧清单改名 `.contest_tasks.json.bak` 备档再覆盖——防拆了一半丢进度，前端确认弹窗）。
- **事件词表**（`events.py` 单源扩展）：`task_planning`、`task_executing`；compile / fix / verify 复用既有词表。
- **前端**（`index.html` 卡 11 内新子区 + JS 迁入 `static/js/ui/*`，纯函数入 `static/js/fx/*`）：拆解按钮 → 任务卡网格（状态徽章 / 分值点引用 / 前置依赖 / 补充框 / 做这一步 / 跳过 / 重做 / 人工改标 / 回滚）+ 执行结果面板（diff + 状态 + 报错摘要）；「直接深化」按钮保留（移到任务区作为兼容入口）；修订执行后提示重新拆解。UI 簇按既有 `frontend-es-modules-stage2` 迁移规则。
- **词表**：「任务推进」/「任务卡」/「拆解」/「重新拆解」进 CONTEXT.md（生成后阶段词表续行）。

## 测试决策

- **只测外部行为**：LLM 一律走既有假 LLM 先例（结构化输出解析 / 整文件输出）。
- **任务模型与解析**：`parse_task_plan` 合法 / 畸形（缺字段、错误类型、空清单）→ 重试兜底 / 拒收，照 `parse_score_points` 先例。
- **落盘**：写读 roundtrip + 形状校验 + 缺文件 = 未拆解 + 坏 JSON = 400；与既有生成文件零交叉（缺省路径下生成产物逐字节不变——既有逐字节断言先例）。
- **`run_task`**：假 LLM → main.c 写盘断言（逐字节对比假 LLM 输出）；备份存在；编译三态（绿 = verified / 无工具链 = unverified / 修一轮仍红 = failed）——照 `test_deepen.py`（内存目录 + 假编译）。补充框 note 进 prompt（假 LLM 捕获断言）。
- **状态转移**：状态机纯函数测试（合法 / 非法转移：`pending → verified` 拒绝等）；人工改标落盘。
- **重拆解**：旧清单 `.bak` 备档 + 新清单覆盖；无旧清单时直接生成。
- **修订联动**：修订执行后任务文件删除 + 前端提示（后端断言删除，前端断言提示）。
- **前端纯函数**：任务卡渲染 / 状态徽章文案 / 补充框状态（`fx` 单源先例 + `fx-guard` 兜底）。
- **测试先例**：`test_deepen.py` / `test_selection.py`（parse 先例）/ `test_context_manifest.py`（落盘先例）。

## 范围外

- 不做任务增删编辑器（增删改任务 = 重新拆解覆盖，用户拍板）。
- 不做 AI 自动连做（逐任务手动点，用户拍板）。
- 任务推进只修改 main.c：新增 .c/.h 文件、模块代码改动不在本期（模块进工程走生成链路；超出 main.c 的目标任务在拆解时提示用户在交接提示词 / 模块库完成，或由 AI 在任务描述中标注"需额外文件"——本期不做）。
- 不做任务级多版本历史（每任务只留执行前备份；重做 = 再执行一次）。
- 不自动把任务进度写入 `.contest_context.json`（两个文件职责分开）。
- 不自动触发拆解（按钮触发，省 token 费）。

## 补充说明

- 术语命名：用户口语"继续往后生成、把题目做出来"；spec 定名「任务推进」（task progression）。落 CONTEXT.md。
- 与深化关系：深化 = 一次全填（兼容保留）；任务推进 = 分步填（主入口）。共用编译验证尾段管线。
- 与修订关系：修订改模块集后重生成 → 任务清单作废删除；模块集不变的重生成路径（修订 apply 不重生成时）不影响任务清单。
- 评分点数据源：任务拆解输入 `score_points` 从当前会话推荐结果取；历史目录 / 无评分点时为空（拆解仍可进行，任务不带分值标注）。
