# 10 — 模块自包含门禁：真机编译 35 错全治本（母版聚合头替换的连锁病）

**What to build:** 工单 01 的 include 解析门禁在 2021F 真机编译时漏掉了第二层问题——生成工程照样 35 错。根因链条：

1. **原始工程靠自定义 headfile.h 聚合一切**：2021F/2026C 都在母版逐飞聚合头基础上加了自己的 include（motor.h / pid.h / gray_track.h / ml_mpu6050.h / digit_uart.h + stdio/string/math），extern g_systick 也在里面。模块 .c 只写 `#include "headfile.h"` 就能拿到全部声明。
2. **生成器用母版 headfile.h 替换**（母版 = 平台基础设施，非模块属性）→ 模块的符号声明一夜间全部消失：pid.c 的 pid_t / motorA_dir / yaw_gyro / motorA_duty / t_cross_detect、gray_track.c 的 D1..D8、digit_uart.c 的 NULL、lock_control/uwb_uart 的 g_systick。
3. **模块导入时没把配套带进来**：pid 模块缺 gray_track（巡线/路口/停车检测辅助单元，原始工程 code/gray_track.c/h，从未入库）、缺 motor 与 ml_mpu6050 依赖声明（yaw_gyro/gz/yaw_Kalman 在库里已存在模块 ml_mpu6050！）、.c 也没 include 自己的 .h。
4. **ARMCC 每文件 30 错误即停**，日志看起来"只有 30 条"其实掩盖了更多（sprintf/stdio、fabs/math 等在 30 条之外未报）。
5. **母版字体头聚合 bug**：母版 headfile.h 显式 include `ml_oled_font.h`，而该头在头文件里定义了非 static 的 `const unsigned char OLED_F8x16[][16]`——原始工程只有 ml_oled.c 一个 TU 碰它（headfile.h 不含），母版聚合后每个 TU 各带一份 → 链接 L6200E multiply defined。所有生成工程都会踩（2026C 从未真正链接过，"双题 end-to-end 全绿"实为静态检查绿）。
6. **2026C 车端 g_systick**：extern 在自定义 headfile.h、定义在旧 main.c，两处都随生成丢失 → lock_control.c / uwb_uart.c 未声明。原始工程里 g_systick 实际从不累加（死变量，仅 key_fob 端 isr.c 在加）。

**修复落点（治本 = 模块库/母版，不只补生成产物）：**

- 模块库 `~/.contest_generator/modules/`：
  - pid：code/pid.c 补 include（pid.h / motor.h / gray_track.h / ml_mpu6050.h / digit_uart.h + `<stdio.h>` + `<math.h>`）；收编 gray_track.c/h（从原始工程字节复制入模块 code/）；manifest dependencies += motor, ml_mpu6050，files += gray_track.c/h。
  - digit_uart：code/digit_uart.c 补 `<stddef.h>`（NULL）。
- 母版 `~/.contest_generator/masters/stm32/`：
  - ml_libs/headfile.h：摘除 `ml_oled_font.h` 聚合（字体头只由 ml_oled.c 自含，与原始工程拓扑一致；想直接用字模的模块自己 include）→ 根治 L6200E。
  - ml_libs/ 新增 ml_systick.h/c：`extern volatile uint32_t g_systick` + `systick_init()` + SysTick_Handler 递增（平台基础设施；模块不得声明对功能库依赖，母版必有）。与 ml_delay 忙等 SysTick 互不冲突（delay 不使能 TICKINT）。
- 门禁 `src/contest_generator/generator.py`：
  - 新增 `_check_module_self_include`：模块 .c 必须 include 本模块自己的至少一个头（错误类 ModuleSelfIncludeError(GeneratorError)，已登记 400 分支）；include 解析只查"引用的头存在"，此规则补"该引用的头在不在"。**符号级完整性只有真编译能证**——静态门禁不替代编译。
  - tests/fakes.py 与 tests/generate_wiring_fakes.py 的假模块补自包含（顺带更真实）。
- 真机脚本 `.scratch/real-run/generate_check.py`：新增 `uv4_build()`——生成后直接 UV4 命令行编译断言 0 错误（KEIL_UV4 环境变量可覆盖路径，无 Keil 机器跳过并明示）。这是工单 01 "真机编译"承诺的真正回归接缝。

**Blocked by:** 无

**Status:** resolved（待用户 Keil GUI 复验）

## Answer

- [x] 反馈环：`UV4.exe -j0 -b Project.uvprojx` 命令行编译（1 秒，红 35 错）——首次建立真机回归环
- [x] 模块库 4 处修复（pid includes + gray_track 收编 + manifest 依赖、digit_uart stddef）
- [x] 母版 3 处修复（headfile 摘字体聚合、ml_systick 服务入库 + **母版 uvprojx 工程树补 ml_systick.c 引用**——生成时 patcher 只注册模块文件，母版树在蒸馏时定死，新文件不进树就永远不会被编译；2021F 恰好无人引用 g_systick 掩盖了这一点）
- [x] 真机验证：2021F 走完整管线（推荐→骨架→生成→UV4）0 错 2 警（主循环 unreachable/无换行，无害）；2026C 直接骨架→生成→UV4 也 0 错（5 警：config.h 与 ml_led.h 的 LED_GPIO 宏重定义 + main.c 无换行，无害）
- [x] 2026C 完整管线被推荐收敛循环的补问卡住（"题面中要求序号2的内容缺失"）——设计行为，待用户补题面原文或回答后重跑
- [x] 门禁 `_check_module_self_include` + 回归测试（tests/test_generator.py），全套 764 绿
- [x] generate_check.py 加 uv4_build 断言（无 Keil 跳过），真机编译进真机验证脚本
