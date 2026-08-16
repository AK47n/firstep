# 01 — motor mspm0 纯驱动化（剥旧工程逻辑 + deps 清空）

**What to build:** `library/modules/motor`（mspm0）只保留纯驱动 API——`motor_init / motor_set_duty / motor_set_direction / limit_duty`；删除 motor_test / encoder_test / pid_tuning / adjust_head / adjust_motor / adjust_motor_pwm / task 状态机 / PID 变量 / 声光 / OLED / IMU / 巡线逻辑；motor.h 删多余 include 与旧声明；manifest deps 清空、description/notes 同步。

**Blocked by:** 无（spec `.scratch/module-dep-cleanup/spec.md` 已定稿）

**Status:** resolved（2026-08-15）

- [x] motor.c 仅纯驱动 + 必要的 ti_msp_dl_config 宏调用（无 delay/oled/stdio/huidu/imu/led_beep/ntb_time 使用）
- [x] motor.h 仅纯驱动声明（无 huidu.h/imu.h/led_beep.h/ntb_time.h include）
- [x] motor manifest deps == []；description/notes 与代码一致
- [x] 测试：test_module_dep_cleanup.py 真实库不变量 + test_master_embedded.py 同步
- [x] pytest 全绿 + mypy src 干净 + stm32/mspm0 真机编译回归

## Comments

- **实施留痕（2026-08-15）**：motor.c 从 738 行旧工程逻辑削到纯驱动（init/duty/direction/limit + 编码器读）；MOTOR_PID 实例不再被 motor 消费——syscfg_instances 消费者改为 ("pid",)，test_syscfg_prune 同步（motor 裁剪不再保留 TIMER）。
- 真机回归：stm32 冒烟/参考 UV4 0 错 0 警；mspm0 冒烟/参考 gmake 0 错 1 警（基线内）。
