# 01 — 参考条目题型标记（topic_type）

**要做什么：** 参考库条目元数据新增「题型」标记：词表单源 `reference_library.TOPIC_TYPES`（首批 `line_follow`（巡线/循迹决策类）、`generic`（通用决策结构——状态机枚举 + 主循环调度骨架，不限巡线））+ `TOPIC_TYPE_LINE_FOLLOW` / `TOPIC_TYPE_GENERIC` 常量；`ReferenceEntry` 加 `topic_type: str = ""`（空 = 未标记题型，向后兼容；词表外值 = 元数据损坏大声失败，与 platform / anchor_kind 同款 `from_dict` 校验）；`to_dict` 带出字段；`add_reference` / `update_reference` 加 `topic_type` 参数（缺省 ""，词表外 ReferenceError → 400 中文）；webapp `POST /api/references` / `PUT /api/references/{id}` payload 加可选 `topic_type`。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**验收：** 全部 ✓（词表 / 常量 / from_dict / to_dict / add / update / webapp POST+PUT 全部实现并测试；测试 test_reference_library.py 新增 11 条全绿）。

- [x] `TOPIC_TYPES` / `TOPIC_TYPE_LINE_FOLLOW` / `TOPIC_TYPE_GENERIC` 常量 + `validate_topic_type`（返回 None / 抛 ReferenceError「非法题型：…（应为 line_follow、generic）」；空串合法 = 未标记）
- [x] `ReferenceEntry.from_dict`：`topic_type = data.get("topic_type", "")`，非空走 `validate_topic_type`（词表外 = 元数据损坏，与 anchor_kind 非法同款大声失败）
- [x] `to_dict` 输出 `"topic_type": self.topic_type`（向后兼容：旧条目读取 = ""，序列化带出）
- [x] `add_reference` / `update_reference` 加 `topic_type: str = ""` 参数 + 校验（词表外 ReferenceError；空 = 未标记合法）
- [x] webapp `/api/references`（POST）/ `/api/references/{id}`（PUT）：`topic_type=_optional_str(payload, "topic_type") or ""`
- [x] 测试：from_dict 已知/未知/缺省三态；add/update 词表外 400；to_dict 含字段；旧 JSON（无字段）向后兼容读 = ""


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
