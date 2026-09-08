# 03 — 骨架自动全文注入（related_limit=4 + 既有 40KB 均分通道）

**要做什么：** 用户生成骨架时，与选中模块相关的官方例程全文自动注入骨架提示词（top-4），骨架主函数可直接参照官方写法；注入走既有「references 全量回读 + 40KB 参考段按篇均分截断」通道，不出预算、不破坏骨架最坏形态结构测试。generate 阶段不注入（行为不变）。

**被谁阻塞：** 02（相关候选装配参数与清单段预算先例）

**状态：** resolved

- [x] skeleton 路由传 `related_limit=4`；相关条目并入 topic.references 后经既有 build_reference_fulltexts 通道自动注入（无需新通道）
- [x] 骨架 prompt 参考段含自动关联例程标注（沿用手动/锚定来源区分机制）
- [x] 骨架端到端验收：选 mspm0 平台 + adc 相关模块 → 骨架提示词含 ADC12 类例程全文段（按篇均分在 40KB 预算内）
- [x] `test_skeleton_prompt_worst_case_with_references_fits_request_budget` 以自动关联 4 篇为形态核算并更新（维持余量）
- [x] generate 阶段确认不注入参考（回归断言）

---
**验收记录（2026-08）：**

- **装配**：budget 新增 `SKELETON_RELATED_LIMIT = 4`（与 RELATED_CANDIDATES_LIMIT
  同址，注释含 40KB/4 篇均分推导）；webapp 骨架路由 `_assemble_topic_context`
  传 `related_limit=SKELETON_RELATED_LIMIT`，`run_skeleton` 加
  `reference_sources=build_reference_sources(topic)`（与参考全文同源同覆盖）。
  生产链路：webapp 骨架路由 → resolve_topic_context(related_limit=4) →
  references 并入 related → build_reference_fulltexts（既有通道回读）→
  run_skeleton → generate_skeleton → _generate_main_c → llm.generate_main_skeleton
  （五参） → _skeleton_user_prompt（参考段标题行 related 条目带标注）。
- **标注**：`SKELETON_RELATED_ANNOTATION = "（与题面 / 模块相关，自动关联）"`
  （llm.py 常量区，与推荐清单段 source_notes 的「自动列出」分属两阶段语境，
  各自单点维护）；`build_reference_sources`（generator.py）与
  `build_reference_fulltexts` 同覆盖（共享 `_reference_entry_ids` 单点）。
- **分派收敛**：_generate_main_c 由「两/三/四参」阶梯收敛为「两参（零注入）
  / 五参（任一注入形态）」两态——消灭逐参加分支的生长源（双轴审查意见
  Repeated Switches / 分派不变量）。
- **测试**（+4 用例与 2 处改造）：
  - 覆盖说明：端到端只验证注入与来源标注，不验证预算切分——按篇均分
    （per_ref = 40KB // 篇数）由 prompt 单元层/worst-case 结构测试承担
    （per_ref 取整逻辑在该层有断言，e2e 复测属重复覆盖，接受现状）。
  - tests/test_llm.py：`test_skeleton_prompt_annotates_related_reference_sources`
    （related 标注 / 非 related 与 None/空零回归）+ 
    `test_generate_main_skeleton_forwards_reference_sources`（五参透传进
    user 消息）；worst-case 测试改 4 篇自动关联形态（per_ref =
    SKELETON_REFERENCE_TOTAL_BYTES // SKELETON_RELATED_LIMIT，断言余量 ≥10KB
    保持 + 标注计数 = SKELETON_RELATED_LIMIT）。
  - tests/test_webapp.py：`test_skeleton_related_references_auto_injected`
    端到端（mspm0 + 选中 adc 模块 → slug 词表映射 → 5 条未锚定 ADC12 候选
    top-4 注入 + related 来源标注 + 0 分 GPIO 对照不入 + 锚定条目照旧并入）；
    `test_generate_with_topic_id_keeps_selected_modules_only` 补生成回归断言
    （skeleton_ref_calls == []——生成阶段不触骨架参考通道，验收点 5）。
  - tests/fakes.py：FakeLLM.generate_main_skeleton 加 reference_sources 参数 +
    skeleton_source_calls 记录。
  - 全量 3156 passed（工单 02 基线 3153 + 本工单净增 3 用例）。
- **真实库冒烟**（.scratch/ref-related-autoload/smoke_skeleton_related.py，
  related_limit=4，真实 library/）：
  2026H/mspm0（adc,uart,oled）→ related 3 条全 ADC12 系（14位分辨率 /
  事件同步 / 事件同步-停止模式，全文 7.8-9.9KB 各篇）；
  2021F/stm32（xunji,key,oled）→ 1（无线串口模块资料）；
  2024H/mspm0（adc,pwm_motor,xunji）→ 4（26H-滚球巡线决策例程 + 3 条
  ADC12——top-4 截断验证）；2026C/stm32（uart,key,oled）→ 1（无线串口）；
  no-topic 粘贴题面（串口通信与 ADC 采样，定时器中断采集电压，OLED 显示）
  → 4（32位定时器 PWM 2 条 + ADC12 定时器触发 2 条，题面双词命中）。
  死库激活 + 上限截断 + 全文回读链路全部验证通过。
- **code-review 双轴完成**：Spec 轴 5 验收点全部对账达成、无缺口、无生产
  蔓延；3 条实现问题全部整改——①`build_reference_fulltexts` 补调
  `_reference_entry_ids`（同覆盖单点契约真正执行，原只 sources 单侧调用）；
  ②骨架标注字面量提常量 SKELETON_RELATED_ANNOTATION；③_generate_main_c
  分派收敛两态（见上）。Standards 轴无硬违反；4 条 judgement call 整改：
  ①覆盖单点——同 Spec ①；②标注字面量——同 Spec ②；③分派梯队——同
  Spec ③；④测试脆弱——worst-case 与端到端断言改引用
  SKELETON_RELATED_LIMIT 常量（不硬编码 4），端到端断言的 id/标题两域
  混比解耦（`_wire_related_adc_entries` 返回 add_reference 实际派生的
  id→标题映射，断言全按 id 域：related < adc_pool / 0 分对照不入 /
  全文注入按 `/* {标题} */` 查——原 `related < set(RELATED_ADC_TITLES)`
  是 id 集比标题集，仅靠 _sanitize_id 对中文标题恒等而通过）——该项为
  提交后补充审查发现，见 follow-up commit。

**状态变更历史：**

- 2026-08：ready-for-agent → claimed → resolved（本券记录）
