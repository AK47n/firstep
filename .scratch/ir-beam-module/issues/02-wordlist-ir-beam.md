# 02 — 词表「感知传感器」补红外对射方案并挂库内 ir_beam

**要做什么：** 买件指引（库外建议/买件商量）命名被硬件词表硬约束——词表新增「红外对射传感器（遮挡检测）」选购方案，`lib_modules=["ir_beam"]` 使界面显示「库内已有：ir_beam」徽章（fx/recommend.js 渲染），买件通道与库内推荐双向闭环。

**被谁阻塞：** 01（ir_beam 模块已在库内，wordlist 机械校验引用存在性）。

**状态：** resolved

- [x] wordlist.json「感知传感器」组新增方案：name / interface（三线制 GPIO）/ price / note（含 ir_beam 驱动说明 + IR_BEAM_BLOCKED_LEVEL 极性提示）/ suitable / lib_modules=["ir_beam"]；recommended 不设（若设需守组内 ≤2 惯例）。
- [x] `tests/test_wordlist.py` 真词表回归（名字精确匹配 + 字段级断言，zigbee-link/03 先例）。
- [x] 提交信息中文，工单状态 resolved。

**验收记录：**
- `test_wordlist.py` 全绿（含新回归 + 既有 lib_modules 引用存在性校验——引用 ir_beam 命中 01 工单已入库的 slug）。
- 应用端无需改动：fx/recommend.js 对 lib_modules 非空方案渲染「库内已有：ir_beam」徽章；买件商量 AI 可从词表选中该方案名（词表 = 库外建议 name 唯一合法来源）。
