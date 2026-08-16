# 02 — motor stm32 补统一 API（与 mspm0 对偶）

**What to build:** stm32 motor 模块补 `motor_set_duty / motor_set_direction / motor_encoder_read`，与 mspm0 同名同义；旧 API（motorA_duty/motorB_duty/encoder_init/extern 变量）保留兼容；manifest description 改双平台统一。

**Blocked by:** 无

**Status:** resolved（2026-08-15）

- [x] motor_stm32.h 声明三个统一 API（duty 范围 0~50000，direction 0停/1正转/2反转，encoder read 读后清零）
- [x] motor_stm32.c 实现：方向映射（统一 1/2 → stm32 0/1）、停止 = duty 0、编码器读清零
- [x] motor manifest description 双平台统一 + stm32 notes 补 API 说明
- [x] 测试 test_module_motor_parity.py + pytest 全绿 + mypy 干净
- [x] 真机：stm32/mspm0 冒烟 + 参考路径编译回归 PASS

## Comments

- stm32 旧语义 0=正转/1=反转（pid.c 注释），统一 API 做映射 `(direction==1)?0:1`；停止 = 占空比 0，方向位保持——与 mspm0 语义一致。
