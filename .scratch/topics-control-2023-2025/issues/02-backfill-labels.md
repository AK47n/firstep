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

**状态：** ready-for-agent

**验收：** 全部 ✓（15 条 manifest 均含合法 category；`list_topics` 全库无空串、词表外零值；topic.md / PDF / programs 与补标前逐字节一致（git diff 仅 manifest）；pytest 全绿；git 提交含 15 个 manifest 变更）。

- [ ] 补标脚本/测试：15 条逐条核对题名 + 写 category（`{**data}` 保留字段）
- [ ] 全库断言：所有条目 category ∈ ("control", "other") 且非空
- [ ] git diff 核实：仅 manifest.json 变更（无 topic.md / PDF 动）
- [ ] pytest test_topic_library.py 全绿（含跨条目全库校验测试）

**参考：** spec 三-B 补标表。
