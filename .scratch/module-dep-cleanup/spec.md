# 模块依赖清理：旧工程逻辑剥离 + 编码器计数归属修正——功能规格

> 2026-08-15 grilling 定稿（用户逐轮确认："按你推荐的来"+ Q3 追问编码器归属后定：不复制变量，迁到 motor 用 API 暴露）。

## Problem Statement

部分模块带着从旧工程提炼时残留的逻辑与依赖：motor（mspm0）里塞了 PID 速度环、加权质心巡线、陀螺姿态控头、声光提示、OLED 自检、task 状态机，导致它 include `huidu.h / imu.h / led_beep.h / ntb_time.h / oled.h / delay.h`；key（按键）模块却持有电机编码器计数与 GROUP1 中断；xunji 通过 extern 引用 key 的计数变量、manifest 却声明了不存在的 pid 依赖；uwb_uart 使用了 filter 却未声明。学生选一个模块被拖进一堆无关模块。

## Solution

按 ADR 0009（模块 = 纯驱动切片）清理：

1. **motor（mspm0）纯驱动化**：只保留 `motor_init / motor_set_duty / motor_set_direction / limit_duty` + 编码器计数（`motor_encoder_read`）。删除 motor_test / encoder_test / pid_tuning / adjust_head / adjust_motor / adjust_motor_pwm / task 状态机 / PID 变量 / 声光 / OLED / IMU / 巡线逻辑。motor 不再依赖 delay / oled / led_beep。
2. **编码器计数归属 motor**：`counter_1_A / counter_2_A` 与 `GROUP1_IRQHandler` 从 key.c 迁入 motor.c；xunji 通过 `motor_encoder_read()` 读计数（xunji 本就依赖 motor，不新增依赖），不再 extern key 的变量。key 变回纯按键模块。
3. **依赖声明修正**：xunji deps = `["motor"]`（删 pid）；uwb_uart deps = `["config", "filter"]`（补 filter）。
4. **manifest 同步**：motor / key / xunji / uwb_uart 的 description、notes、pins 与代码一致（key 只留 KEY_START 引脚）。

## User Stories

1. 作为学生，我选 motor 只得到电机驱动 + 编码器读数，不被拖进 OLED / 蜂鸣器 / IMU / 灰度 / 延时模块。
2. 作为学生，我选 key 只得到按键读取，不被拖进编码器中断。
3. 作为学生，我选 xunji 自动带上 motor（巡线需要电机），不会因为漏选 key 而链接失败。
4. 作为学生，我选 uwb_uart 自动带上 filter，单选也能编译。
5. 作为学生，我想做速度闭环时调 `motor_encoder_read()` 就能拿左右轮编码器读数。

## Implementation Decisions

- 纯驱动边界：motor mspm0 = PWM 调速 + 方向 GPIO + 编码器计数（GROUP1_IRQHandler 是编码器硬件中断，归属 motor 与 stm32 侧 motor_stm32.c 的 EXTI 计数对偶）。
- `motor_encoder_read(int32_t *left, int32_t *right)`：读 counter_1_A/counter_2_A 并清零（替代 xunji 原 extern + 清零逻辑）。
- key.c 只保留 `get_key_state`；GROUP1_IRQHandler / counter 定义迁 motor.c；key.h 不变。
- motor.h：删 `huidu.h / imu.h / led_beep.h / ntb_time.h` include 与 test 声明；加 `motor_encoder_read`。
- uwb_uart：filter 是真实依赖（uwb_uart.c include filter.h 并调用滤波接口），补声明，不改代码。
- 删除的旧逻辑不归档——已在参考文件库 `car-1-1-巡线模板-mspm0`（2024H 锚定）与 xunji/pid 模块中有普适替代。

## Testing Decisions

- 新测试文件 `tests/test_module_dep_cleanup.py`，对真实库（`library/modules`）做数据/代码不变量：
  - motor.c 含 counter 定义 + GROUP1_IRQHandler + motor_encoder_read，不含旧逻辑符号（adjust_motor_pwm / motor_test / pid_tuning / huidu_value / current_attitude / OLED_ / led_on / beep_on）。
  - key.c 不含 GROUP1_IRQHandler / counter；key manifest pins 只有 KEY_START。
  - xunji.c 调 motor_encoder_read、不 extern counter；xunji manifest deps == ("motor",)。
  - motor manifest deps == ()；uwb_uart deps == ("config", "filter")。
- 更新 `tests/test_master_embedded.py::test_motor_manifest_stm32_entry_files_exist`（motor deps 断言改空）。
- 真机回归：stm32 2021F/2026C + mspm0 2024H 生成编译（UV4/gmake 0 错）。

## Out of Scope

- 不改 stm32 侧 motor_stm32.c / pid.c / filter 实现。
- 不新增“编码器模块”——编码器计数随 motor（两平台对偶）。
- 不修 mspm0 syscfg 中 MOTOR_PID_INST 未用实例（留待后续工单观察）。

## Further Notes

- 审计脚本 `.scratch/real-run/audit_module_deps.py` 留档；本次清理后重跑应只剩零告警。
