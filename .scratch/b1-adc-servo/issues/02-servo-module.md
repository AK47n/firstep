# 02 — servo 模块落地（双平台）

**要做什么：** 模块库出现 servo（舵机角度）模块：双平台自有文件（servo_stm32.c/h 基于母版 ml_pwm 封 50Hz/0.5-2.5ms 脉宽角度映射；servo_mspm0.c/h 基于 PWM 跨族迁移底座，pin_family 双分支照 motor 先例）；统一 API servo_init/servo_set_angle(0-180°)；manifest 声明 pwm 引脚角色（类型级可绑）；推荐链路自动命中；结构测试与骨架接口块测试通过。

**被谁阻塞：** 无——可立即开始（与 b1 01 并行）。

**状态：** resolved

- [x] 模块库 library/modules/servo/manifest.json 可解析（slug/描述四要素/pins 校验通过），双平台条目各带 .c/.h
- [x] 双平台 API 对偶：servo_init(servo_id, channel) / servo_set_angle(servo_id, angle)（0-180°，越界钳位），角度换算常量（周期 20ms / 脉宽 0.5-2.5ms / 占空比换算）模块头文件单源
- [x] stm32 实现走 ml_pwm（pwm_pin_init/pwm_init/pwm_update，MAX_DUTY=50000）；mspm0 实现走 PWM 底座（pin_family.h 双分支，TIMG/TIMA 都可用）
- [x] pins 声明 pwm 角色与默认脚（双平台板定义可绑，绑定渲染正常）
- [x] 结构测试：manifest 形状 / 无题绑定 / API 对偶断言 / 角度换算边界（0/90/180° 占空比正确）
- [x] build_skeleton_interfaces 选中 servo 后接口块含 servo_init/servo_set_angle
- [x] 全量测试通过


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
