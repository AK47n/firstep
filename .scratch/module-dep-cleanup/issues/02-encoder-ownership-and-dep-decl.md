# 02 — 编码器计数迁入 motor + 依赖声明修正（xunji/key/uwb）

**What to build:** 编码器计数归属 motor（mspm0）：`counter_1_A / counter_2_A` 与 `GROUP1_IRQHandler` 从 key.c 迁入 motor.c，motor 暴露 `motor_encoder_read(left, right)`；xunji.c 改调 `motor_encoder_read`、删 extern；key 变回纯按键（key.c 去计数/中断，manifest pins 只留 KEY_START，description/notes 同步）；xunji manifest deps = `["motor"]`（删 pid）；uwb_uart manifest deps = `["config", "filter"]`（补 filter）。

**Blocked by:** 01（同改 motor.c，串行避免冲突）

**Status:** resolved（2026-08-15）

- [x] motor.c 定义 counter_1_A/counter_2_A + GROUP1_IRQHandler + motor_encoder_read；motor.h 声明 motor_encoder_read
- [x] key.c 只保留按键读取；key manifest pins == [KEY_START]、description/notes 同步
- [x] xunji.c 使用 motor_encoder_read、不 extern counter；xunji manifest deps == ["motor"]
- [x] uwb_uart manifest deps == ["config", "filter"]
- [x] 测试：test_module_dep_cleanup.py 真实库不变量（motor 有编码器符号 / key 无 / xunji 走 API / deps 钉）
- [x] pytest 全绿 + mypy src 干净 + stm32/mspm0 真机编译回归

## Comments

- **实施留痕（2026-08-15）**：DC_MOTOR 实例消费者从 (motor,key) 改为 (motor,)——test_pins.py 默认值映射删 key 4 条编码器条目；test_pin_bindings 槽位冲突/去重测试改用 huidu.L1 × pid.GRAY_D1（同默认 PA22 同 HUIDU 槽位）。pid manifest notes 同步编码器来源（motor_encoder_read）。
- 真机回归：stm32 冒烟/参考 UV4 0 错 0 警；mspm0 冒烟/参考 gmake 0 错 1 警（基线内）。审计脚本 audit_module_deps.py 复跑零告警。
