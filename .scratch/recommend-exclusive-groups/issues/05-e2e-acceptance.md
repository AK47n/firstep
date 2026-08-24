# 05 — 端到端验收（2024H 真跑 + stm32 回归）

**要做什么：** 真跑 2024H 推荐（MSPM0）验证两个原始投诉都修好：①不再出现双
8 路灰度配置（pid/xunji 只一个进已选）；②航向保持卡出现（AI 命中或 hint 兜底），
用户可换选 imu_uart / ml_mpu6050。stm32 出题回归无组卡、行为不变。更新
CHANGELOG 并回归全套测试。

**被谁阻塞：** 01、02、03、04

**状态：** ready-for-agent

- [ ] 真跑 2024H AI 推荐（MSPM0）：done 载荷带 gray-track + attitude-hold 组卡；推荐结果无重复灰度配置（同组只一个进 selectedSlugs）；姿态组卡出现（AI 命中或 hint）
- [ ] 组卡交互实测：换选 xunji → 已选只剩 xunji；再点取消 → 整组移除；展开/引脚配置无重复 8 路灰度
- [ ] stm32 赛题回归：无组卡、chips 行为与现状一致；旧推荐缓存渲染不变
- [ ] 全量 pytest + mypy src 干净；CHANGELOG 中文条目

**Notes:**（实现后填）
