# 03 — 双平台编译矩阵验收（adc + servo）

**要做什么：** 含 adc / servo 模块的生成工程在两条平台线都编译 0 error 0 warning：stm32（UV4 真机验收脚本或等价编译路径）+ mspm0（gmake 全量重建，含 SysConfig 生成头）；引脚绑定渲染（pin_config.h / mspm0.syscfg $assign）回归不破；生成门禁（含 pwm/adc 类型级绑定、定时器实例冲突）全绿。

**被谁阻塞：** b1/01（adc 模块落地）、b1/02（servo 模块落地）。

**状态：** resolved

- [ ] stm32 生成工程（选 adc + servo + 必要依赖，默认脚）UV4 编译 0 error 0 warning
- [ ] mspm0 生成工程（同模块集）gmake 全量重建 0 error（syscfg ovsRate 等基线 warning 照既有记录处理）
- [ ] 绑定场景：把 adc 绑到非默认脚、servo 绑到另一 TIM 通道脚 → 渲染正确且编译通过
- [ ] 生成门禁回归：pwm/adc 类型级校验、定时器实例冲突门禁不误报
- [ ] 验收脚本/测试与生产同闸（照 generate-check-parity 先例，产物树重建语料跑同一套门禁）
