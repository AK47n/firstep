# 04 — 前端功能组选择卡（单选交换 / 取消 / 去重 / 警告）

**要做什么：** 推荐结果里同功能模块以「功能组选择卡」呈现（组内每个成员带差异
定位与 AI 推荐徽标），用户单选一个——换选即替换（不叠加），再点取消整组；AI
同组多推时只把第一个加进已选；需求清单里组内成员不再渲染成重复 chip；已选里
出现同组多选时黄字警告。旧载荷（无 exclusive_groups）渲染不变。

**被谁阻塞：** 02（done 载荷形状）

**状态：** ready-for-agent

- [ ] 组卡渲染（评分点面板后、需求清单前）：label + hint 卡「AI 未推荐，题面疑似需要——请确认」标注 + 成员行（radio/slug/role/「AI 推荐」徽标与理由）
- [ ] 单选交互：点击 radio → selectedSlugs 移除同组其他成员后加入该成员；再点已选成员 = 取消整组（从 selectedSlugs 移除）
- [ ] autoAdd 同组去重：data.modules 逐个加入时，同组已有成员在 selectedSlugs → 跳过后续同组推荐（仅首个入集）
- [ ] 需求清单 chips：组内成员的 slug 不再渲染成独立 chip，改为「已在『功能组选择』中」灰注（需求句/理由可见性保留）；非组模块 chips 交互不变
- [ ] renderSelected 兜底：selectedSlugs 同组 ≥2 成员 → 黄字警告（共用同一硬件，建议只留一个），不硬拦
- [ ] js 单测（tests/js/*.test.mjs 既有形态）：渲染（radio/徽标/role/hint 标注）、autoAdd 去重、换选 swap、取消、同组多选警告、旧载荷容错；pytest 全绿

**Notes:**（实现后填）
