# 工单 03：任务清单微编辑 + 调序后端（task_progress + webapp + 测试）

Status: resolved

## 目标

实现 spec 第 5-6 条用户故事后端：任务卡字段微编辑（标题/描述/依赖/验收方式/评分点）与上移/下移调序（id 不变，依赖引用稳定），同步端点。

## 交付

- **task_progress.py**：
  - `update_task_fields(plan, task_id, *, title=None, description=None, depends_on=None, verify=None, score_refs=None)` 纯函数：None = 保留原值；title/description 非空否则 TaskError；verify 词表外 → TaskError；depends_on 1 起序号转 id、越界/未知 → TaskError；score_refs 字符串数组校验；status/note/dialog_note/needs_redo/iterations 一律保留。
  - `move_task(plan, task_id, direction)` 纯函数：up/down 相邻换位（数组顺序即展示顺序）；越界（首 ↑ / 末 ↓）→ TaskError；id 不变。
  - backup_task_plan 复用（编辑/调序前备份，照 insert_task_from_idea 先例：**先校验后备份再写**——backup 是 move 语义）。
- **webapp.py**：
  - `POST /api/tasks/idea/edit`：{output_dir, task_id, fields{title?, description?, depends_on?, verify?, score_refs?}} → 校验 → 备份 → 写盘 → {task, plan}（清单未拆解/任务不存在 → 400 中文）。
  - `POST /api/tasks/idea/move`：{output_dir, task_id, direction} → {plan}。
- 测试：test_task_progress.py（update 合法/非法各分支/保留字段断言/move 边界与 id 不变）+ test_webapp.py（edit/move 200 + 400 分支）；全量 pytest 绿。

## 验收

1. edit 改 title/description/depends_on/verify/score_refs 落盘；status/needs_redo/轮次历史保留。
2. edit 非法输入（空标题 / 未知依赖 / verify 词表外 / 依赖引用自己）→ 400 中文，清单未变。
3. move up/down 换位落盘；id 不变；首卡 ↑ / 末卡 ↓ → 400。
4. 编辑/调序前 .bak 备份（可经任务清单恢复先例回滚）。
5. 全量 pytest 绿（既有 2670 + 新增）。
