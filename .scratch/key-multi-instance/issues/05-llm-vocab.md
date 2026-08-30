# 05 — llm 变体词表泛化（提示词 + 输出契约）

**要做什么：** AI 推荐链路认识 key 的变体词表：多实例规则段与输出契约里的
「变体可选值」从 led 单表（red/yellow/green）泛化为按 slug 词表（策略表投影），
提示词里 key 的内置变体 = start/stop/mode/set 或空串。词表单源纪律保持：
提示词可见契约与解析校验同源。

**被谁阻塞：** 04（策略表 key 行 = 词表单源就位）。

**状态：** resolved

**评审结论（2026-08-31 双轴评审）：** Standards 无硬违规。三处评议整改：① 变体
中文标签移入策略表单源（MultiInstancePolicy.variant_label：led=颜色、key=功能
）+ multi_instance_labels 投影——消除「token 在策略、标签在 llm」的两处真源
（Shotgun Surgery）；② 删除已无消费方的 LED_COLOR_MACROS 死别名；③ per_module
与契约 token 并集统一按策略登记序（消除循环序不一致）。契约并集拍平（AI 只读
契约可能跨模块填错 token）= 判断项接受：规则段逐模块约束，契约仅为形状提示。
工单项 3（2026C/2022C/2026F 真实推荐数量）行为归 07 抽验（issue 已声明）。
822 passed（llm/selection/multi-instance/webapp）。

- [x] 多实例规则段：每个多实例模块标出各自内置变体词表（led = 颜色 red/yellow/green，
      key = 功能 start/stop/mode/set），词表来源 = 展开策略表投影，零硬编码副本。
- [x] 输出契约示例同步泛化（同一投影来源），旧库（无多实例模块）提示词仍逐字节
      不变（条件段先例）。
- [x] AI 按题面猜 key instances：2026C 一键启动 → 1 实例（start）；2022C/H 启动 +
      设置 → 2 实例（start/set）；2026F 三键 → 3 实例（可见数量即可，变体可空串）。
- [x] 非多实例模块带 instances 仍整轮拒收（既有校验不放松）；多实例数量无上限
      守卫（expand 层）/ 题面无数量省略 instances（既有契约）对 key 生效。

**验收标准备注：** 提示词段 / 契约文本单测（含 word-for-word 断言）验收；
AI 实测推荐行为归 07 端到端或人工抽验。
