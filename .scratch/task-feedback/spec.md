# 任务上板反馈闭环（task-feedback）

## 问题陈述

任务推进（task-progress）已能拆解任务、逐卡执行、编译验证。但真实场景是：学生执行完一个任务后**上真板/真车**验证，大概率一次做不对——会有小瑕疵；发现瑕疵后需要把实际情况告诉 AI，AI 修改，再上板验证，循环直到用户确认没问题才打勾进入下一口。

现状缺口：任务卡只有一次性「补充框（note）」附着在执行提示词里；执行完的轮次（改了什么、编译结果、备份点）没有记录；已通过的任务发现新问题无法直接反馈重开；「标记已验证」是二元动作，中间没有反馈迭代通道。

## 方案

任务卡新增**「上板反馈」闭环**：

1. 用户在卡上描述上板实测现象（如「左轮不转」「灰度读不到」）；
2. 触发一轮执行闭环（复用现有 run_task：LLM 按反馈修复 → 整树备份 → 写盘 → 编译 → diff 展示）；
3. 每轮记入任务卡的**迭代历史**（轮次、反馈文本、修改 diff、编译结果、备份点），全部备份保留，可回滚到任意轮；
4. 用户满意 → 确认通过（打勾）→ 进入下一任务；不满意 → 继续反馈，直到满意。

**灵活确认**：不设强制上板门禁。compile 类任务编译绿仍自动 verified（上板看不出来的任务不拦）；但任何状态（含已验证）的任务都有「上板反馈」入口——已验证任务触发反馈时自动重开（revert 到 pending 后执行）。

## 用户故事

1. 作为学生，我执行完任务后上真车跑，发现瑕疵，我在卡上描述现象，AI 按反馈修改，我能看到本轮 diff 和编译结果。
2. 我可以多轮反馈（每轮独立备份），直到我满意为止。
3. 我满意后点「确认通过」（打勾），任务标记已验证，进入下一任务。
4. 我可以查看任务的历史轮次（每轮反馈 + 结果），也能回滚到任意一轮。
5. 已通过的任务我发现新问题，可以直接反馈，自动重开。
6. 上板看不出来的任务（如纯软件初始化），我不需要上板，编译绿即通过。

## 实现决策

1. **无新状态**：确认通过 = 现有 unverified→verified 转移（打勾按钮=「确认通过」文案）；已验证任务反馈 = 先自动 apply_task_status(verified→pending，转移表已合法) 再执行。
2. **feedback 是 execute_task 的可选参数**：新增独立 prompt 段「上板实测反馈」；与 note（执行前说明）分两段；prompt 明确「按反馈修复指定任务，只改相关部分，不重写无关代码」。
3. **迭代历史数据模型**：新 `TaskIteration`（seq/kind=execute|feedback/feedback/status/backup_id/compile_summary/at），`Task.iterations: tuple[TaskIteration, ...] = ()`；`.contest_tasks.json` shape 向后兼容（旧清单无 iterations 读回为空）。
4. **每轮状态回填按任务 verify 类型**（复用现有逻辑）：compile 类反馈轮编译绿 → verified；manual 类编译绿 → unverified（待人工确认）。
5. **回滚端点** `POST /api/tasks/rollback-iteration`：{output_dir, task_id, seq} → 恢复该轮备份（复用 restore_revision）→ **撤销语义**：备份 = 该轮执行前的整树快照（备份在写盘前），故回滚后代码回到该轮执行前、任务状态恢复为该轮之前的终态（向前找最近历史轮次的 status；无前轮 → pending）→ 落盘。迭代历史本身保留（留痕可追溯）。
6. **全部备份保留**（用户拍板）：一轮几十 KB~几 MB，整题十几轮可接受。
7. **反馈校验**：feedback 必为非空字符串（strip 后）；空串等同不传。
8. 事件复用 task_executing/compile_start/fix_start/verify_result（不新增事件词表）。

## 测试决策

- task_progress：初始执行记轮、反馈轮追加、旧 shape 兼容、回滚端点状态回填、已验证自动 revert、状态回填两类型（manual→unverified / compile→verified）。
- llm：execute_task feedback 参数解析、prompt 段快照（feedback/note 两段独立）。
- webapp：execute 端点 feedback 校验 + rollback-iteration 端点。
- JS：taskCardActions 加反馈按钮显隐、轮次历史渲染、回滚按钮。
- 全量 pytest + node --test + mypy 回归。

## 范围外

- 不做强制上板门禁（用户已拍板「灵活确认」——上板看不出差异的任务不强求）。
- 不做自动连续反馈（每轮由用户手动触发；AI 不自主循环）。
- 不改 compile 类「编译绿=已验证」的自动语义。
- 不做任务级多版本历史（任务清单整体重拆仍走 force 备档）。
- 不做多任务并行。

## 补充说明

- 反馈 note 与补充框的区别：note = 执行前一次性说明；feedback = 上板后实测现象，按轮记录可追溯。
- 轮次历史随任务清单落盘 `.contest_tasks.json`；修订重生成（模块集变）仍作废整份清单。
