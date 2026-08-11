# 01 — mspm0 模块缺口补录：2026H 5 模块已闭环（98f8b0a 合入）；剩余 = 2024H 巡线题专用层补录（car xunji 原生）

**What to build:** 2026-08-11 MSPM0 线真机验收（2026H 题）发现 mspm0 线模块库只有 9 个，H 题实际需要的 pid（摆杆/滚球控制）、digit_uart（视觉坐标串口）、filter（滑动滤波）、gray_track（巡线路口检测）、ball_detect（球检）全在库外——推荐只能给库外建议，生成工程里这些功能全是 TODO。**2026H 部分已于并行会话实施完毕（98f8b0a，2026-08-11 从桌面 worktree 合入 main）**；**剩余缺口 = 2024H 巡线题专用层**：mspm0 巡线三层中灰度读取（huidu）与循迹核心（motor 内嵌 adjust_motor_pwm）已在库，题专用决策层（白区计数路口 / AB-ABCDA-ACBDA 模式状态机 / 声光）缺失——源 = car xunji 原生真机工程（2026-08-11 领域建模定判据：补录移植源原生优先，见 CONTEXT.md「入库路径」）。

**Status:** resolved（2026-08-12 剩余 2024H 巡线题专用层实施完毕，验收两项勾选，见下）

## 已完成：2026H 5 模块（98f8b0a，2026-08-11 合入 main）

- **pid**：mspm0 = 26H H 题滚球版（pid_mspm0.c/h + gray_track_mspm0.c/h，一圈巡线 + 启停线停车 LAP 状态机 + ball_detect 球坐标解析）。依赖映射：motorA_duty→motor_set_duty(id,duty)；dir→motor_set_direction(id,dir)（0停1正转2反转）；Encoder_count1/2→key counter_1_A/counter_2_A；gz→imu_uart gyro_dps_raw（extern 符号级引用）；MAX_DUTY=1300。stm32 21F 版不动
- **digit_uart**：mspm0 = DIGIT_UART（UART1/PA8/PA9，母版 syscfg 新增）RX 中断 + 环形缓冲 + CSV 帧解析，解析逻辑与 stm32 版一致
- **filter**：纯 C 无平台差异，mspm0/stm32 共用同一文件（include headfile.h→stdint.h 类型等价）
- **ball_detect**：新建模块——stm32 = 26H 提取（USART1 语义）+ mspm0 = DL_UART 移植（DIGIT_UART 实例）
- **ml_mpu6050**：mspm0 空 files 条目（依赖跨平台共享兼容；mspm0 姿态由 imu_uart 承担）
- **验证**：out_2026H_mspm0 扩 12 模块 gmake 全量 0 错（sysconfig 0 err + 编译 0 err + 链接出 .out）；**未上板**（如实记录）；全量 pytest 1009 绿 + mypy src 干净
- **遗留**：gray_track D1-D8 ↔ HUIDU 宏映射为编译级默认（物理排列按实际接线调整）；ball_detect/digit_uart 的 UART1_IRQHandler 需用户 main.c 挂载

## 剩余需求：2024H 巡线题专用层补录

1. **移植源（2026-08-11 领域建模修订：原生平台真机代码优先，见 CONTEXT.md「入库路径」）**：首选原生 mspm0 真机工程 `sources/car/car xunji`（Debug/PWM.out 真机编译产物在，与 car 1.1 同源、已归档为 car-1-1-巡线模板-mspm0 参考）——巡线套装源 = control.c 的白色区域计数路口检测 + AB/ABCDA/ACBDA 模式状态机 + 声光 + xunji_template 加权质心核心，适配默认外设布局宏（GPIO_Gray_* 8 路 → HUIDU_L3/L2/L1/R1/R2/L4/R3/R4，对照 huidu/motor manifest 宏名；DC_MOTOR/编码器/定时器同理）；已入库的 26H gray_track_mspm0 只含 26H 启停线检测，**不覆盖 2024H 路口/模式状态机**。stm32 21F 实现（gray_track.c 十字路口语义）仅作对照参考，仅当原生源缺能力时才走 DL_xxx driverlib 移植。
2. **验证**：补录后必须真机编译（默认外设布局已含 MOTOR_PID/NTB/DC_MOTOR/HUIDU 宏，工单 mspm0-syscfg-default 已落地 c1c9f72）——"无编译验证的代码不入库"（motor mspm0 悬空代码教训）。
3. **依赖与自包含**：manifest dependencies 按实际 include 声明（stm32 先例：pid 依赖 motor/gray_track/ml_mpu6050）；`_check_module_self_include` 门禁要求 .c 自含头。
4. **verified 语义**：编译过但未上板 = verified true 或标注"编译验证未上板"（参考 stm32 先例），工单里如实记录。
5. **命名与硬件绑定**：巡线套装模块标注"2024H 巡线题专用"（对偶 stm32 pid 的"2021F 巡线题专用"）；car xunji 陀螺仪为 JY61P（USART_JY61P），与库内 imu_uart（IMU601 UART0）不同件，补录时按需取舍并如实标注硬件绑定。

## 素材到位（2026-08-11 记录，暂缓解除）

- **首选原生源**：`sources/car/car xunji`（mspm0 真机工程，Debug/PWM.out 在）——control.c（白区计数路口 + AB/ABCDA/ACBDA 状态机 + 声光）+ xunji_template.c/h（加权质心核心）+ xunji_logic_spec.md（AI 可读规格）
- **已归档副本**：`library/references/car-1-1-巡线模板-mspm0/`（同源 + 规格文档）
- **用户提供完整 TI SDK**：`C:\ti\mspm0_sdk_2_00_01_00\`——149 个官方 driverlib 例程正对 LP_MSPM0G3507（目标器件同型号）+ `source/ti/driverlib/` 全量源码。SDK 不入仓库（5.7GB 级），实施时用绝对路径引用
- **仓库备份素材**：`sources/materials/MSPM0_MOTOR参考例程/`（7343e80 入库）——MSP_Motor_Ctrl（Modbus 电机控制 + 编码器解析 + CRC16）、m0imu（UART 陀螺仪）、empty.syscfg + ti_msp_dl_config.h/c 真机生成物、移植.md（DL_* API 用法手册）
- **遗留风险（如实记录）**：仍是"编译验证未上板"级——真机素材替代不了实际接线/上板行为验证；入库标准 = gmake 编译 0 错

## 验收（2026H 部分已勾选 = 98f8b0a；2024H 部分已勾选 = 本次提交）

- [x] 5 模块 manifest：platforms.mspm0 + files + dependencies 按实际 include 声明，`_check_module_self_include` 门禁过
- [x] 每个模块编译验证：默认外设布局生成工程 gmake 0 错（无编译验证不入库）
- [x] 全量 pytest 绿 + mypy src 干净
- [x] 工单如实记录"编译验证未上板"状态
- [x] **2024H 巡线套装模块**：manifest platforms.mspm0 + files + dependencies，标注"2024H 巡线题专用"，编译验证 gmake 0 错
- [x] 2024H mspm0 全管线生成验证（推荐 2024H 题 → 巡线套装模块可被选中 → 产物编译 0 错）

## 实施记录（2024H 巡线题专用层补录，2026-08-12）

- **模块**：`library/modules/xunji/`（manifest.json + code/xunji.c/h，slug `xunji`）——description 含"2024H 巡线题专用"（topic_library `related_module_slugs` 自动发现命中，全管线实测 `related=['xunji']`）
- **移植源**：`sources/car/car xunji/control.c`（原生 mspm0 真机，Debug/PWM.out 编译产物在；归档副本 `library/references/car-1-1-巡线模板-mspm0/` 逐字节一致，2026-08-11 领域建模判据：原生平台真机代码优先）——白区计数路口（8 路全白 100ms 消抖）+ AB/ABCDA/ACBDA/ACBDAx4 状态机（对 2024H 题 1~4 问）+ 声光（真机仅 LED 无蜂鸣器）+ xunji_centroid 加权质心核心逐字保留
- **硬件适配**（母版默认外设布局宏，对照工单第 19 行）：
  - 灰度 8 路 `GPIO_Gray_1..8` → `HUIDU_L3/L2/L1/R1/R2/L4/R3/R4`（huidu 模块索引序，编译级默认，实际接线改 xunji.c 头部 P1..P8 宏；极性非零=白与 26H gray_track_mspm0 同款直读）
  - 电机：`GPIO_IN_PIN_AIN*/BIN*` → `motor_set_direction(id,dir)` 0停1正转2反转；PWM 真机百分比制（TIMG0 2500 计数）→ `motor_set_duty` 原始值 0~1300（MAX_DUTY=1300 对偶 pid_mspm0）
  - 编码器：真机四倍频正交解码 GROUP1_IRQHandler → key 模块 `counter_1_A/counter_2_A`（单沿计数无方向，extern 符号级，需同选 key；xunji_tick_50ms 采样清零）
  - 陀螺仪：真机 JY61P（UART2 0x55 帧）≠ 库内 imu_uart IMU601（UART0 CRC16 帧）——本模块消费 `current_attitude.yaw`（imu_uart，类型经 motor.h→imu.h 链），掉头角常量（103/error=180）与 Yaw 零偏/极性需上板校准（manifest `hardware_bound: true` 如实标注）
  - 声光：`GPIO_LED`(PA26) → `LED_BEEP_LED`(PA3)；STBY（真机 PA7）母版硬件直连 3.3V（motor.h），ACBDAx4 关使能动作省略
- **调度**：真机 50ms/10ms 定时中断拆为 `xunji_tick_50ms()`/`xunji_tick_10ms()`，main 周期调用（`MOTOR_PID_INST_IRQHandler` 已被 motor 模块占用，按 pid_mspm0 先例自建定时器中断或主循环分频）
- **依赖**：dependencies `["motor"]`（实际 include motor.h；imu_uart 经 motor.h→imu.h 链带入；key 计数符号级 extern——需手动同选小车栈，motor manifest 同款约定）；`_check_module_self_include` 门禁过（xunji.c 自含 xunji.h）
- **验证**：
  - 模块级：默认外设布局工程（out_2026H_mspm0 + xunji）`build_makefiles.py` + `gmake all` **0 错 0 警**，mspm0_project.out 链接成功
  - 全管线：`generate_check.py --platform mspm0 --clarify clarify_2024H.json --add delay,ntb_time,oled,key 2024H` → 推荐 4 轮收敛**选中 xunji**（related=['xunji'] 自动发现 + AI 理由"2024H 巡线工程的状态机与巡线控制"）→ 生成 out_2024H_mspm0（含 xunji 文件）产物门禁全过 → gmake **0 错**（3 警告均非本模块：母版 syscfg UART ovsRate ×2 + AI 骨架 main.c 未用变量）→ mspm0_project.out 链接成功
  - 补问一轮预置：模型问场地布局（A/B/C/D 与半圆弧布置、直线段有无引导线），clarify_2024H.json 按题目文本作答（"场地除两个半圆弧外不得添加任何标记"→ 直线段无引导线，弧线段灰度循迹、直线段陀螺仪航向保持）
  - **编译验证未上板**（真机素材替代不了实际接线/上板行为验证，如实记录）
  - 全量 pytest **1087 绿** + mypy src 干净
- **build_makefiles.py**：MODULES 表补 `("xunji", ["xunji.c"])`；新增按工程实际模块集过滤（工程按推荐集生成，模块子集因题而异——2024H 无 digit_uart/filter/ball_detect/pid，表内其他条目不写进 makefile）
- **遗留（如实记录）**：灰度物理排列/极性、Yaw 零偏与掉头角常量需上板校准；key 单沿计数无方向（真机四倍频正交解码）；tick 挂载由 main 完成（自建定时器或主循环分频）；ml_mpu6050 在推荐集（mspm0 空 files 条目，不参与编译）

## 实施提示词（复制到新会话）

```
实施工单剩余部分 .scratch/mspm0-modules-backfill/issues/01-backfill.md（2024H 巡线题专用层补录）：
1. 读工单（剩余需求节 + 素材到位节）+ CONTEXT.md「入库路径」词条（原生优先判据）
   + library/modules/pid（先例：刚合入的 26H mspm0 版 pid_mspm0/gray_track_mspm0，
   D1-D8 ↔ HUIDU 宏映射已有一份编译级默认）+ library/modules/huidu（HUIDU 宏名）
2. 素材（都本地可读）：
   - 首选原生源：sources/car/car xunji（mspm0 真机工程，Debug/PWM.out 在）——
     control.c 白区计数路口 + AB/ABCDA/ACBDA 状态机 + 声光；xunji_template.c 加权质心
   - 已归档副本：library/references/car-1-1-巡线模板-mspm0/（同源 + xunji_logic_spec.md）
   - 对照（仅缺能力时）：21F stm32 gray_track.c（十字路口语义）+ TI SDK 例程
3. 补录巡线套装模块（标注"2024H 巡线题专用"），manifest 补 platforms.mspm0 +
   dependencies + files；GPIO_Gray_* → HUIDU_L3/L2/L1/R1/R2/L4/R3/R4 适配；
   JY61P 与 imu_uart 不同件，按需取舍并标注硬件绑定
4. 编译验证（硬门槛）：默认外设布局生成工程 gmake 0 错才入库（c1c9f72 已落地）
5. 全量 pytest + mypy
6. 提交（data: 前缀，模块库数据）+ 推送
```
