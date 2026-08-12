# 05 — lock_control / zone 决策剥离（2026C 数字钥匙，可解散）

**What to build:** 2026C 数字钥匙双模块按 ADR 0009 处理：决策层移出——lock_control 的 zone/event 状态机 + 迎宾声光时序、zone 的感应/迎宾/解锁区域划分（题定义）→ 骨架；驱动层评估去留：lock_control 剩余 = LED 三色 + 蜂鸣器驱动，与 led_beep 模块重叠 → **优先解散**（驱动并入 led_beep 或功能库，模块删除，决策进骨架）；zone 剩余 = 测距/方位数据处理驱动 → 评估并入 uwb 类模块或解散。解散与否实施时按代码定细界，结果与理由记录在工单。**先决依赖：工单 01 已闭环（结构测试 + EXCEPTION_REGISTRY 例外注册表已立）——本工单清理 lock_control/zone 后必须删除注册表对应两条目（不删 = 存量校验红）。注意：2026C 生成链路（generate_check.py 真机验收脚本）引用这两模块——解散后需同步检查生成用例（红证/绿证）。**

**Status:** drafted

## 实施（细节实施会话定）

1. 决策剥离：lock_control.c 状态机/时序/事件 → 骨架（2026C 题生成时 AI 写）；zone.c 区域划分 → 骨架。
2. 驱动评估：LED 三色 + 蜂鸣器 → led_beep 模块（当前 mspm0 版，评估加 stm32 平台条目）或 stm32 功能库 gpio 直用；测距/方位处理 → uwb 类模块或解散。
3. 解散动作：模块目录删除 + manifest 清理（若被推荐/生成引用需登记，2026C 骨架的 deps 改由保留模块承担）。
4. 结构测试 EXCEPTION_REGISTRY（tests/test_module_universality.py）删除 lock_control / zone 两条目——不删 = 存量校验红；解散（目录删除）也必须删条目。
4. generate_check.py / 真机用例同步：2026C 生成 → UV4 编译验证。

## 文件边界

- library/modules/lock_control/*、library/modules/zone/*
- library/modules/led_beep/*（若并入 stm32 条目）
- 交叉：2026C 生成链路（generate_check.py 用例、推荐引用）
- **不动**：uwb_uart / zigbee_uart / config 模块内容

## 验收

- [ ] stm32 UV4 编译 0 错（2026C 全管线：推荐 → 骨架 → 生成 → 构建，模块保留或解散后的新形态）。
- [ ] 结构测试绿（lock_control / zone 不再命中黑名单；解散则无此二模块扫描对象）。
- [ ] 解散/保留决定有记录（工单写明结果与理由）。
- [ ] 2026C 生成用例同步过（生成不引用已删模块）。
- [ ] EXCEPTION_REGISTRY 已删 lock_control / zone 条目（解散则随目录删除一并删），删后全库测试仍绿。
- [ ] 工单补实施记录 + 验收勾选，Status resolved。
