# 04 — 前端功能组选择卡（单选交换 / 取消 / 去重 / 警告）

**要做什么：** 推荐结果里同功能模块以「功能组选择卡」呈现（组内每个成员带差异
定位与 AI 推荐徽标），用户单选一个——换选即替换（不叠加），再点取消整组；AI
同组多推时只把第一个加进已选；需求清单里组内成员不再渲染成重复 chip；已选里
出现同组多选时黄字警告。旧载荷（无 exclusive_groups）渲染不变。

**被谁阻塞：** 02（done 载荷形状）

**状态：** resolved

- [x] 组卡渲染（评分点面板后、需求清单前）：label + hint 卡「AI 未推荐，题面疑似需要——请确认」标注 + 成员行（radio/slug/role/「AI 推荐」徽标与理由）
- [x] 单选交互：点击 radio → selectedSlugs 移除同组其他成员后加入该成员；再点已选成员 = 取消整组（从 selectedSlugs 移除）
- [x] autoAdd 同组去重：data.modules 逐个加入时，同组已有成员在 selectedSlugs → 跳过后续同组推荐（仅首个入集）
- [x] 需求清单 chips：组内成员的 slug 不再渲染成独立 chip，改为「已在『功能组选择』中」灰注（需求句/理由可见性保留）；非组模块 chips 交互不变
- [x] renderSelected 兜底：selectedSlugs 同组 ≥2 成员 → 黄字警告（共用同一硬件，建议只留一个），不硬拦
- [x] js 单测（tests/js/*.test.mjs 既有形态）：渲染（radio/徽标/role/hint 标注）、autoAdd 去重、换选 swap、取消、同组多选警告、旧载荷容错；pytest 全绿

**Notes：**（2026-08-24 实现，3 文件）
- 纯函数层（组卡渲染 / 单选交换取消 / autoAdd 去重 / 冲突判定）全部下沉：`groupOfSlug` / `applyGroupRadio` / `autoAddDedup` / `groupConflicts` / `renderGroupCards` / `groupRequirementNote`（index.html，插在 renderScorePointPanel 后、renderRecommendResult 前），照 score-points-format 先例从 HTML 正则抽函数体喂 node:test，不碰 DOM/fetch；交互 = 点击 radio → applyGroupRadio → 清 expanded/warnings → 重绘（用 click 而非 change——再点已选 radio 不触发原生 change，取消整组会丢）。
- 组卡区 = scorePanel 后、需求清单前；hint 卡带「AI 未推荐，题面疑似需要——请确认」；成员行 radio+slug+role+「AI 推荐」徽标与理由；默认选中 = 组内当前在 selectedSlugs 的成员，多个按 data.modules 序（AI 推荐序）取第一个、不在 data.modules 的按成员登记序兜底（spec:107）。
- autoAdd 去重 = `autoAddDedup`（首个推荐成员入集，其余仅徽标）；需求 chips = 组内 slug 改灰注「已在『功能组选择』中」；同组多选警告 = renderWarnings 内 `.warn-box.group`（黄字不硬拦）——落点在 renderWarnings 而非 renderSelected：警告盒本就归 renderWarnings 渲染，且所有 renderSelected 调用点（9 处）均紧跟 renderWarnings，选择变化各路径警告全覆盖（双轴审查明确确认无功能缺口）。
- 旧载荷（无 exclusive_groups）＝ `|| []` 容错，无卡、autoAdd 行为与现状一致。
- 测试：tests/js/group-cards.test.mjs +15（渲染/hint 标注/默认选中序/XSS 转义/旧载荷/autoAdd 去重/换选/取消/未知组/冲突/灰注/接线断言）；JS 全量 142 passed；pytest 2288 passed（51.7s，与基线持平）；mypy src 0 错误。
- 双轴审查（基线 d5e40d1，双后台子代理）：Standards 轴**无硬违规**，判断项 4 条——①两个点击回调重复 re-render 尾部 → 提 `reRenderAfterSelectionChange` 共用；②`groupDefs` 全局与 lastRecommend 双源 → 删除全局，改读 `(lastRecommend || {}).exclusive_groups || []`；③`!groupPanel` 字符串真值 → 改 `!groups.length`；④applyGroupRadio 命名（用户建议名，保留）。Spec 轴**通过**：6 条 AC 全满足，唯一提示 = 冲突警告落点 renderWarnings（非 renderSelected），已确认功能等价。
- 验证：整改后 JS 全量 142 passed、内联脚本 new Function 语法检查通过。
