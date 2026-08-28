# 工单 05：想法草稿箱后端（drafts.py + webapp + 测试）

Status: resolved

> 修订说明（双轴评审）：端点测试归入 test_drafts.py（与 chat/insert 端点
> 测试同族惯例——tasks_client/全流程断言就近维护），非 test_webapp.py；
> 落盘只做原子写（工单允许的两选一），不另设 .bak。

## 目标

实现 spec 第 7-8 条用户故事后端：想法草稿工程目录落盘（`.contest_ideas.json`），读/增/删端点，同文本去重。

## 交付

- **drafts.py（新模块）**：`IdeaDraft{id, text, at}` + `IDEA_DRAFTS_FILENAME = ".contest_ideas.json"`；load/save/empty/list/add（去重：同 text 已存在 → 不重复插入）/delete（未知 id 静默）；add 时 text 空/纯空白 → TaskError；坏 JSON → TaskError 400 中文；id 生成照先例（uuid4 hex 或时间戳+序）。
- **webapp.py**：
  - `POST /api/tasks/idea/drafts/read`：{output_dir} → {drafts}（无文件 = []，不 400）。
  - `POST /api/tasks/idea/drafts/add`：{output_dir, text} → {drafts}。
  - `POST /api/tasks/idea/drafts/delete`：{output_dir, id} → {drafts}。
  - 备份：add/delete 前备份（.bak，照清单文件先例；或仅 save 原子写——按 task_progress 清单既有实现对齐）。
- 测试：test_drafts.py（模型/落盘/坏 JSON/add 去重/delete/空 text 400）+ test_webapp.py（三路由 200/400）；全量 pytest 绿。

## 验收

1. add 落盘；重复同文本 add → 不新增（去重）。
2. delete 删除指定 id；未知 id → 不报错。
3. read 无文件 → []; 坏 JSON → 400 中文。
4. 全量 pytest 绿（既有 2670 + 新增）。
