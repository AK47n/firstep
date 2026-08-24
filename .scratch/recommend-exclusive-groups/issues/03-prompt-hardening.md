# 03 — 提示词强化（用户消息段：同组互斥 + 题面核查）

**要做什么：** AI 推荐时不再同组多推（同一传感器只荐一个），无引导线直线行驶的
题面必须命中「航向保持」组至少一个模块。规则放**用户消息段**（教训先例：只改
系统提示词会被用户消息尾句盖过），与多实例规则段同款条件段先例（库内存在组才
出段，预算零成本）。

**被谁阻塞：** 01（摘要行组标注已生效，规则段条件 = 库内存在组）

**状态：** resolved

- [x] `_selection_user_prompt` 增条件段：「同组互斥（硬约束）」——清单带「同组互斥」标注的模块共用同一传感器/同一功能，同一题内只推荐一个；同组多个被推荐 = 配置页出现两份相同硬件配置（2024H 复盘）；按题面择优推荐一个，其余候选由系统展示给用户选择
- [x] 题面核查条：「无引导线/无其他指示标记/沿直线自主行驶 → 必须从『航向保持』组推荐一个；漏推荐 = 直线段无法完成」（条件：库内存在航向保持类组）
- [x] 契约/预算断言更新：新增段字节计入 SELECT 最坏形态与余量断言（tests/test_llm.py）；新旧路径断言（库无组 = 逐字节不变）
- [x] pytest 全绿 + mypy src 干净

**Notes:** 实现：`_selection_user_prompt` 多实例规则段后、输出契约前插入两个条件段。
组统计从 `manifest_summaries` 投影（零参数传递）：`group_stats`（组 id →
(该平台成员数, label)）→ 成员数 ≥2 才出「同组互斥（硬约束）」段——**单成员组
视图（stm32 形态：gray-track 仅 pid、attitude-hold 仅 ml_mpu6050）不出段**
（Spec 轴审查发现的 spec:159 漏洞「单成员组 → 无提示词段」已修）；attitude 类组
判定用常量 `ATTITUDE_GROUP_ID_PREFIX = "attitude"`（前缀魔法串单源）；核查条
组名取库内实际 label（不硬编码）；「同组互斥」标注词提为
`manifest.EXCLUSIVE_GROUP_TAG` 常量（to_line 标注与规则段正文共用，单源）。

测试：`test_selection_prompt_carries_exclusive_group_rules` 四路径（双组两段都出
且均在契约前 / 仅灰度组只出互斥段 / stm32 单成员视图两段都不出 / 无组缺省两段
都不出）+ `_grouped_summary` 助手；预算最坏形态测试的摘要改带两组声明（14 条中
4 条），断言 8KB→6KB 硬保证，docstring 记录修订 3：实测 124143 字节、余量
6929B ≈ 6.7KB（按工单授权精确记数——spec.md 不固化实测数，只留描述）。

双轴审查（基线 c91c9d1，双后台子代理）：Standards 轴**无硬违规**，判断项 4 条
全处理：①「同组互斥」词手写两处（to_line + 规则段）+ 测试 → 提
EXCLUSIVE_GROUP_TAG 单源；②attitude 前缀魔法串 + 硬编码组名 → 前缀常量 + label
取库内；③预算数双源（spec + docstring）→ spec 去实测数，只留 docstring 修订 3；
④最坏形态措辞（4/14 带组）→ docstring 注明真实 stm32 线仅 2 条带组，此为安全
上界。Spec 轴**通过**：唯一实质发现 (c)-1 单成员组未排除（stm32 会误触发规则段
违反 spec:159）→ 已修（成员计数 ≥2）+ 新测试路径；另两处轻微（核查条组名硬编码
→ 已改取库 label；startswith 前缀 → 已提常量）。

验证：受改测试 5 passed；test_llm.py 全 250 passed；mypy src 0 错误（60 文件）；
真实库冒烟 mspm0 视图两段均出、stm32 视图均不出；预算实测 124143/余量 6929 与
docstring 一致；全套 pytest 2288 passed（51s）。
