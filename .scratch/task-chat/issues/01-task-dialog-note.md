# 工单 01：任务对话结论字段（dialog_note）落盘 + 执行注入 + 采纳端点

**要做什么：**任务级「对话采纳结论」字段贯通：Task 模型加 `dialog_note` → 落盘读回 → 执行 prompt 注入 → 采纳/清除端点。

**被谁阻塞：**无（本工单最先；spec `.scratch/task-chat/spec.md` 已定案）。

**状态：** resolved（双轴评审通过 + 整改）

## 验收标准

- [x] `Task` dataclass（task_progress.py:143-176）加 `dialog_note: str = ""`，to_dict/from_dict 带出读回；旧清单（无该字段）读回 = 空串，不报错（TASKS_MANIFEST_VERSION 不变）。
- [x] `_with_task_status`（task_progress.py:692-734）重建 Task 时保留 dialog_note：新参数 `dialog_note: str | None = None`（None = 保留原值，与 note/iterations 同款）；现有调用零行为变化。
- [x] 新域编排 `set_task_dialog_note(output_dir, task_id, text) -> dict`（返回 `{"task", "plan"}`，照 apply_task_status 先例：读清单 → find_task（TaskError）→ 替换 → 写盘）；text 非字符串上层校验；text 空串 = 清除采纳。
- [x] `llm._task_execute_user_prompt`（llm.py:3561-3596）加 dialog_note 段：读 `task.get("dialog_note", "")`，非空时在【用户补充说明（note）】段之后、【上板实测反馈（feedback）】段之前插入【用户沟通结论（采纳自对话，按此修正实现）】段；空 = 无该段（既有形状逐字节不变）。`execute_task` 协议签名零变更（run_task 传 task.to_dict() 已带该字段）。
- [x] 新端点 `POST /api/tasks/dialog-adopt`（同步，webapp.py 任务端点区）：`{output_dir, task_id, text}`；text 非字符串 → TaskError 400 中文；输出目录不存在/未拆解/任务不存在 → TaskError 400；返回 `{"task", "plan"}`。
- [x] 测试：test_task_progress.py（dialog_note 往返/旧清单缺省/保留与替换/采纳落盘/清除/未知任务）；test_llm.py（prompt 段注入位置与空形态）；test_webapp.py（adopt 200/400）；fakes.py 无须改（execute_task 签名未变）。
- [x] 全量 pytest + mypy 改动文件 0 错；中文 commit（.githooks/commit-msg 强制）。

## 评审记录

双轴 code-review（git diff cd00038...94425fd）：Standards 0 硬违规（本工单相关：无未登记异常、域编排校验前置落盘、向前兼容读、prompt 空段形状不变）；Spec 0 项本工单问题（c 项两处归工单 03；c3 message 双通道归工单 02，均已整改）。判断项记录：Data Clumps（执行上下文五元组为 run_task/execute_task 先例惯例，接受）。
