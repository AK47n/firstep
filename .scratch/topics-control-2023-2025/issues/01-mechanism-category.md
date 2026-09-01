# 01 — 题库分类标记机制（category 词表 + 透出 + 前端筛选）

**要做什么：** 赛题条目新增「控制题/其他」分类标记（照参考库 topic_type 先例：reference_library.py TOPIC_TYPES / validate_topic_type / from_dict 校验 / 词表端点 GET /api/references/topic-types）：

- `topic_library.py`：
  - 词表常量 `TOPIC_CATEGORIES = ("control", "other")` + `validate_topic_category(value)`——词表外抛 `TopicError`（中文「非法分类：…（应为 control、other）」）；**空串合法 = 未标记**（向后兼容，照 topic_type 先例）。
  - `TopicEntry`（L134 frozen dataclass）加 `category: str = ""` 字段；`to_dict`（L157）带出 `"category"`；manifest 读取（`_load_entry`）缺省 `""`、词表外值**大声失败**（照元数据损坏哲学，与 platform / anchor_kind 同款）。
  - `TopicDraft` 加 `category: str = ""`；`parse_confirm_entries`（L498）解析 `item.get("category", "")` 并走词表校验——category 是**用户提交值**（拆条确认表单），不由 LLM/AI 标注。
  - `confirm_topics`（L171）：manifest 写入加 `"category"`（与 year/number/problem_md/original_pdf/programs 并列）。
  - `update_topic`（L425）：加 `category: str` 参数，成为第四个**可编辑字段**（现有三个：problem_text / programs / hint_module_groups）；身份不变量不变（year / number / original_pdf / problem_md 不可改）；manifest 更新用 `{**data, ...}` 保留既有字段；写入失败恢复题面旧值契约保持。
- `webapp.py`：
  - `PUT /api/topics/{key}`（L4752）：body 契约加 `category`（全量必填；词表外 400 中文，照「programs 必须是字符串列表」同风格）。
  - `POST /api/topics/confirm`（L4709 附近 parse_confirm_entries 路径）：entries 项加可选 `category`。
  - `GET /api/topics`（L4649）/ `GET /api/topics/{key}`（L4783）：经 `to_dict` 自动透出（零额外改动，验证即可）。
  - 新增 `GET /api/topics/categories` -> `{"categories": ["control", "other"]}`（照 `reference_topic_types` L4448 先例）；**路由顺序陷阱**：必须注册在 `GET /api/topics/{key}`（L4783）之前，否则 `categories` 被当 key 解析。
- 前端 `static/js/fx/topic.js` + `ui/topic.js`（+ 对应测试 test/js）：
  - 题库列表加「全部 / 控制题 / 其他」筛选下拉（选项单源 `GET /api/topics/categories`）；
  - 条目 chip 显示分类（「控制题」「其他」徽标，照参考库 topic_type chip 先例 `js/fx/reference.js` + `ui/reference.js`）；
  - 拆条确认表单 + 编辑表单加分类下拉（新建默认 `control`——控制题专项定位；选项同单源）。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

**验收：** 全部 ✓（词表 / validate_topic_category / TopicEntry / to_dict / manifest 读写 / confirm / update / PUT / categories 端点 / 前端筛选+标签+表单，全部实现并测试；pytest test_topic_library.py 新增全绿、js 测试全绿、仓库语言检查通过）。

- [ ] `TOPIC_CATEGORIES` 常量 + `validate_topic_category`（空串合法；词表外 TopicError 中文；照 validate_topic_type 测试三态）
- [ ] `TopicEntry.category` 字段 + `to_dict` 带出 + `_load_entry` 读取（缺省 ""、词表外大声失败）
- [ ] `TopicDraft.category` + `parse_confirm_entries` 解析校验（缺省 ""）
- [ ] `confirm_topics` manifest 写入「category」（含事务与 git 提交不变）
- [ ] `update_topic` 加 category 参数（可编辑第四字段；身份键不可改；`{**data, ...}` 保留既有字段；写失败回滚契约保持）
- [ ] webapp PUT body 加 category（词表外 400）+ confirm entries 加可选 category + 新增 GET /api/topics/categories（路由在 /api/topics/{key} 之前）
- [ ] 前端：筛选下拉（单源端点）+ 条目标签 + 拆条确认/编辑表单下拉（默认 control）
- [ ] 测试：pytest（词表三态 / manifest 读写 / to_dict / update 权限 / confirm 落盘 category / categories 端点）+ js（筛选 / chip / 表单）全绿

**参考：** `.scratch/topic-framework/issues/01-topic-type-label.md`（题型标记先例：词表/校验/from_dict/to_dict/add/update/webapp 全链）。
