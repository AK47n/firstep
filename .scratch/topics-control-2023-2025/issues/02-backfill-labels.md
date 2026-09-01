# 02 — 15 条老条目分类补标（category 全量回填）

**要做什么：** 现有 15 条赛题条目补 `category`——**只改每条的 manifest.json**（加 category 字段），不动 topic.md / PDF / programs / hint_module_groups；update 后的全库断言（list_topics 全部条目 category ∈ 词表且非空）通过，提交自动生效（git 提交）。判定依据以各条目 topic.md 题名/正文为准，逐条复核；与下表不一致时以复核结果为准并在工单记录：

| 条目 | 题名（判定依据） | category |
|---|---|---|
| 2018C | 无线充电电动小车 | control |
| 2019A | 电动小车动态无线充电系统 | control |
| 2020C | 坡道行驶电动小车 | control |
| 2021F | 智能送药小车 | control |
| 2022C | 小车跟随行驶系统 | control |
| 2022H | 小车跟随行驶系统（高职/赛区版） | control |
| 2024H | 自动行驶小车（巡线） | control |
| 2026A | AC-AC 变换电路 | other |
| 2026B | '无源'交流电流表及无线读表器 | other |
| 2026C | 基于无线通信的数字钥匙实验系统 | other |
| 2026D | 陆空协同无人机系统 | control |
| 2026E | 拼图装置 | control |
| 2026F | 李萨如图形显示控制装置 | other |
| 2026G | 周期信号测量分析装置 | other |
| 2026H | 车载平衡滚球运动控制系统 | control |

实现方式：一次性脚本（或 pytest 参数化）读 manifest → 写 `{**data, "category": value}`（`write_json` 原语，保留既有字段）→ 每条 `commit_after_write`（或统一一次提交）；**不走 update_topic**（它是题面/程序全量保存，补标只需 manifest 单字段）。

**被谁阻塞：** 01（机制先上——manifest 读取/词表校验不存在时无字段可写）。

**状态：** resolved

**验收：** 全部 ✓（15 条 manifest 均含合法 category；`list_topics` 全库无空串、词表外零值；topic.md / PDF / programs 与补标前一致（git diff 仅 15 个 manifest.json，diff 内容仅新增 category 字段）；pytest test_topic_library.py + test_autocommit.py + test_repo_language.py = 176 passed；git 提交含 15 个 manifest 变更 + 补标脚本 + 工单 + CHANGELOG。

- [x] 补标脚本/测试：15 条逐条核对题名 + 写 category（`{**data}` 保留字段）——脚本 `.scratch/topics-control-2023-2025/backfill_categories.py`（幂等：已标目标值跳过、词表外/冲突值失败不覆盖；dry-run 模式）
- [x] 全库断言：所有条目 category ∈ ("control", "other") 且非空——`test_real_topic_library_all_entries_have_category`（TDD 红→绿）
- [x] git diff 核实：仅 15 个 manifest.json 变更（无 topic.md / PDF 动，逐字节保留）
- [x] pytest test_topic_library.py 全绿（含跨条目全库校验测试）

**题名复核记录：** 15 条逐条对照 topic.md 题名/正文，与补标表完全一致（2018C 无线充电电动小车 / 2019A 电动小车动态无线充电系统 / 2020C 坡道行驶电动小车 / 2021F 智能送药小车 / 2022C+H 小车跟随行驶系统 / 2024H 自动行驶小车 / 2026A AC-AC变换电路 / 2026B 交流电流表及无线读表器 / 2026C 数字钥匙实验系统 / 2026D 陆空协同无人机系统 / 2026E 拼图装置 / 2026F 李萨如图形显示控制装置 / 2026G 周期信号测量分析装置 / 2026H 车载平衡滚球运动控制系统），无偏差记录。

**实现方式：** 一次性脚本（非 update_topic——补标只需 manifest 单字段）；read_json → `{**data, "category": value}` → write_json 原语（字段原样保留）；未调 commit_after_write（其 git add 限 library/ 子域，会卷入工作区遗留的 reference.json / 素材清单.txt 变更），改完人工精确 add 15 个 manifest.json 统一一次提交。

**参考：** spec 三-B 补标表。
