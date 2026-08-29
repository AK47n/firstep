# 02 — 步骤报告接线引用协议

**要做什么：** 步骤报告可携带「本步涉及哪几根线」的结构化引用（wiring），AI 只能给名字，后端查表校验、非法丢弃——图由确定性数据画，AI 幻觉进不了盘。

**被谁阻塞：** 01（接线快照落盘）——校验以快照内嵌板定义为优先数据源

**状态：** resolved

- [x] 步骤报告 JSON 契约增加可选字段 `wiring: [{pin, target, note?}]`（缺省 = 空数组 = 本步无物理接线）；旧清单 / 旧轮次迭代读取零改动（向后兼容）
- [x] 系统提示词约束更新：wiring 条目只能引用模块接口清单与板定义里的真实引脚 / 端子名，每根线一条，note 简短中文可选
- [x] 校验纯函数（与 LLM 层解耦，直接可单测）：pin 合法 = ∈ 板定义 pins 名集合（含 power/gnd/reset 类，供 3V3/GND/5V 供电线）；target 合法 = ∈ 本工程模块端子名（声明 id，label 不同时也接受 label）∪ 板定义 fixed 资源名 ∪ 引脚名自身
- [x] 逐条校验：非法条目丢弃、合法保留；剩余 ≥1 条才写入；全非法 = 空数组（供前端走资源高亮退化路径）
- [x] wiring 随步骤报告写入该轮迭代记录落盘（缺省空，向后兼容）；读取侧条目级容错（坏数据 → 空，不 500）
- [x] pytest：合法全过 / 部分非法丢弃 / 全非法 → 空 / 字段缺省 → 空 / 幻觉引脚名（如 PA99）拒收成文

**答案：** 实现：wiring.py 02 层（WiringEntry / parse_wiring_entries / filter_wiring_entries / wiring_source（单入口一次读盘）/ wiring_context / read_wiring_rows / wiring_summary_text）；llm.py StepReport.wiring + TASK_REPORT_SYSTEM_PROMPT 四段契约 + wiring_summary 透传；task_progress.py TaskIteration.wiring + _report_task_step 装配；tests（test_wiring / test_task_progress / test_llm / fakes）。

两轴评审记录：规格轴——6 项验收全过（23 项 pytest 绿），整改 1 项（wiring_context 失败吞主报告 → 已隔离数据源失败，只清空 wiring）；标准轴——无环、无硬性文档违反，整改 2 项：①白名单误滤（wiring_summary_text 角色列是合成串「KEY_START（启动按键）」而验证只收 role_id/label → _row_target_names 增收 role 合成串，fx matchRow 同步，回归测试成文）；②Duplicated Code（wiring_context/read_wiring_rows 各读一次快照 → 合并 wiring_source 单入口，两者变投影）。

**备注：** 本工单只做协议与数据层；前端渲染与展示在工单 04。校验数据源 = 快照内嵌板定义（01 产物），目录无快照时回退静态板定义读取（不阻塞）。
