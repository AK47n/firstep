# 工程说明

## 工程概览

- 平台：TI MSPM0G3507 / CCS
- 开发板：地猛星 MSPM0G3507

## 目录结构

| 目录/文件 | 用途 |
|---|---|
| `modules/` | 选中模块的驱动源码（每个模块一个子目录：.c/.h，已自动加入 CCS 工程与生成器的编译验证） |
| `main.c` | 主程序骨架——赛题逻辑从这里开始（第 8 步骨架、第 11 步任务推进逐步写入） |
| `mspm0.syscfg` | SysConfig 外设布局（时钟 / 外设 / 引脚配置，第 7 步写入——与实际接线一一对应） |
| `Debug/` | CCS 构建产物（makefile 由生成器写入——配置了 CCS 工具链时；*.out 可烧录固件，点击构建后生成） |
| `.ccsproject` | CCS 工程文件——用 CCS：File → Open Project 选择工程目录导入 |
| `.cproject` | CCS 工程文件（与 .ccsproject 同套——无需单独处理） |
| `.settings/` | CCS 辅助配置——无需改动 |
| `targetConfigs/` | 调试器目标配置——无需改动 |
| `README.md` | 本工程说明——目录 / 编译烧录 / 接线 / 验证顺序与「生成后怎么继续」 |
| `演示脚本.md` | 演示流程（按评分点 / 功能需求组织）——答辩演示前看它 |
| `设计报告草稿.md` | 设计报告草稿（可选：AI 方案论证 + 软件流程，供报告参考；未生成 = 正常） |
| `main.py` | K230 / 视觉副产物（可选：选了带 Python 副产物的模块时生成，拷入 SD 卡使用） |
| `mp_deployment_source/` | K230 AI 模型部署包（可选：选了带 AI 模型的模板时生成——部署配置 + .kmodel，连同 main.py 一起拷入 SD 卡 /sdcard/） |
| `.contest_context.json` | 工具上下文清单（本次生成的输入快照——「修订与深化」回读用，勿手改） |
| `.contest_wiring.json` | 接线快照（工具绘制接线图用——勿手改） |

> 本工程由电赛工程生成器构建：main.c 是可编译的骨架/模板，含模块初始化与占位逻辑（TODO 标记）。赛题的实现逻辑需要你核对、补全并上板调试；引脚一致性以 mspm0.syscfg 为准（与实际接线不一致先改这里）。

## 快速上手：编译 + 烧录

用 TI Code Composer Studio（CCS）打开工程：File → Open Project 选择工程目录
构建：点击 Build（或按 Ctrl+B）生成可烧录固件
下载：接好调试器，点击 Debug（或按 F11）下载到 MSPM0G3507

## 引脚接线表

| 模块 | 角色 | 引脚 | 说明 |
|---|---|---|---|
| motor | PWMAB_C0 | PA12 | pwm（必接） |
| motor | PWMAB_C1 | PA13 | pwm（必接） |
| motor | AIN1 | PB9 | gpio_out（必接） |
| motor | AIN2 | PA18 | gpio_out（必接） |
| motor | BIN1 | PB18 | gpio_out（必接） |
| motor | BIN2 | PA7 | gpio_out（必接） |
| motor | AA | PA16 | enc（必接） |
| motor | AB | PA17 | enc（必接） |
| motor | BA | PB19 | enc（必接） |
| motor | BB | PB20 | enc（必接） |
| l298n | L298N_PWM_C0 | PA14 | pwm（必接） |
| l298n | L298N_PWM_C1 | PB24 | pwm（必接） |
| l298n | L298N_EN | PA27 | gpio_out（必接） |
| pid | GRAY_D1 | PA22 | gpio_in（必接） |
| pid | GRAY_D2 | PA23 | gpio_in（必接） |
| pid | GRAY_D3 | PA24 | gpio_in（必接） |
| pid | GRAY_D4 | PA25 | gpio_in（必接） |
| pid | GRAY_D5 | PA26 | gpio_in（必接） |
| pid | GRAY_D6 | PA27 | gpio_in（必接） |
| pid | GRAY_D7 | PB6 | gpio_in（必接） |
| pid | GRAY_D8 | PB7 | gpio_in（必接） |
| led | LED | PA15 | gpio_out（必接） |
| ml_mpu6050 | I2C_0_SCL | PA1 | i2c_scl（必接） |
| ml_mpu6050 | I2C_0_SDA | PA0 | i2c_sda（必接） |

> 其余外设引脚以工程内 pin_config.h（stm32）/ mspm0.syscfg 为准

## 模块清单与依赖

- motor：TB6612 双路直流电机驱动（双平台统一 API）：motor_set_duty 调速 + motor_set_direction 方向 + motor_encoder_read 编码器读数（读后清零）。
- l298n：L298N 大电流电机驱动（双平台纯驱动，ADR 0009）：方向 + 调速形态（页面 AO_Control 原样——IN1/IN2 双通道 PWM、mspm0 另带 EN 使能 GPIO），l298n_init + l298n_set_duty + l298n_set_direction；独立模块不并入 motor：适用于大电流/多路电机、无编码器闭环场景（平衡车/推车/闸机/重载底盘）。（来源：https://wiki.lckfb.com/zh-hans/dmx/module/control/l298n-motor-drive-module.html）
- pid：PID 闭环控制 + 灰度循迹驱动（双平台）：通用 PID 控制器（位置式/增量式，pid_init/pid_cal/pidout_limit）+ 左右轮目标速度输出（含轮速校准，motor_target_set）+ 灰度 8 路读取与边缘中点巡线偏差计算（line_error_calc）+ PD 巡线速度输出（line_pid_track）；适用于巡线/循迹/速度闭环类赛题功能，路口/停车等决策逻辑归生成骨架。（依赖：motor）
- ntb_time：系统毫秒时间戳（双平台统一 get_time_stamp_ms）：mspm0 用 NTB 定时器回绕累加，stm32 用 SysTick 1ms 节拍。
- led：LED 指示灯驱动（双平台）：led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN；拉电流 1=亮 细节已封装在模块内。
- beep：蜂鸣器驱动（双平台）：beep_init/beep_on/beep_off/beep_toggle + beep_beep 响 N 声（阻塞式）。
- delay：MSPM0 毫秒延时：delay_ms 基于 CPUCLK_FREQ 换算调用 delay_cycles，任何时钟频率自动适配。
- led_beep：声光组合模块（双平台）：LED + 蜂鸣器同时开关 + led_beep_alarm 声光报警；只控制一方请选 led 或 beep。（依赖：led、beep、delay）
- ml_mpu6050：MPU6050 六轴传感器的 I2C 通用驱动：提供初始化、寄存器读写以及加速度计和陀螺仪原始数据读取功能，供外部算法进一步解算姿态角；适用于航向保持（车头朝向）、直线行驶纠偏、倾角检测等需要陀螺仪/姿态数据的功能。

## 第三方素材来源

本工程的部分模块驱动改写自立创开发板技术文档中心（wiki.lckfb.com）「地猛星 MSPM0G3507 模块移植手册」（清单行已附原页链接）。立创官网版权声明第三条要求：

> 请大家务必尊重贡献者的智力劳动成果：任何使用该文件的个人或组织，如需使用或者参考手册中的模块资料，将其复制、传播、修改、公开展示或在其他网站上使用，都需要在使用时清楚的标明文件的来源以及链接。

来源：https://wiki.lckfb.com/zh-hans/dmx/

## 评分点验收清单

| 编号 | 分区 | 分值 | 原文句子 | 描述 |
|---|---|---|---|---|
| (1) | 基础 | 20 分 | 句子 24、26、27 | A→B 停车，声光提示，用时≤15s |
| (2) | 基础 | 20 分 | 句子 28、29、30、31、32 | A→B→弧线C→D→弧线A 停车，每点声光提示，一圈≤30s |
| (3) | 发挥 | 30 分 | 句子 33、34、35、36、37、38 | A→C→弧线B→D→弧线A 停车，每点声光提示，一圈≤40s |
| (4) | 发挥 | 30 分 | 句子 39 | 按第3项路径行驶4圈停车，用时越少越好 |
| (5) | 发挥 | 20 分 | 句子 40、41 | 设计报告 |
| total | 未分区 | 120 分 | 句子 97 | 总分 |

## 验证顺序清单

按顺序逐个验证，前一个过了再接下一个

- [ ] led — LED 指示灯驱动（双平台）：led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN；拉电流 1=亮 细节已封装在模块内。
- [ ] delay — MSPM0 毫秒延时：delay_ms 基于 CPUCLK_FREQ 换算调用 delay_cycles，任何时钟频率自动适配。
- [ ] led_beep — 声光组合模块（双平台）：LED + 蜂鸣器同时开关 + led_beep_alarm 声光报警；只控制一方请选 led 或 beep。
- [ ] motor — TB6612 双路直流电机驱动（双平台统一 API）：motor_set_duty 调速 + motor_set_direction 方向 + motor_encoder_read 编码器读数（读后清零）。
- [ ] l298n — L298N 大电流电机驱动（双平台纯驱动，ADR 0009）：方向 + 调速形态（页面 AO_Control 原样——IN1/IN2 双通道 PWM、mspm0 另带 EN 使能 GPIO），l298n_init + l298n_set_duty + l298n_set_direction；独立模块不并入 motor：适用于大电流/多路电机、无编码器闭环场景（平衡车/推车/闸机/重载底盘）。
- [ ] pid — PID 闭环控制 + 灰度循迹驱动（双平台）：通用 PID 控制器（位置式/增量式，pid_init/pid_cal/pidout_limit）+ 左右轮目标速度输出（含轮速校准，motor_target_set）+ 灰度 8 路读取与边缘中点巡线偏差计算（line_error_calc）+ PD 巡线速度输出（line_pid_track）；适用于巡线/循迹/速度闭环类赛题功能，路口/停车等决策逻辑归生成骨架。
- [ ] ntb_time — 系统毫秒时间戳（双平台统一 get_time_stamp_ms）：mspm0 用 NTB 定时器回绕累加，stm32 用 SysTick 1ms 节拍。
- [ ] beep — 蜂鸣器驱动（双平台）：beep_init/beep_on/beep_off/beep_toggle + beep_beep 响 N 声（阻塞式）。
- [ ] ml_mpu6050 — MPU6050 六轴传感器的 I2C 通用驱动：提供初始化、寄存器读写以及加速度计和陀螺仪原始数据读取功能，供外部算法进一步解算姿态角；适用于航向保持（车头朝向）、直线行驶纠偏、倾角检测等需要陀螺仪/姿态数据的功能。

## 生成后怎么继续

回到工具的生成页，按需继续：

- 第 10 步「修复中心」：编译报错时看错误、让 AI 自动修复（工具内即可完成，不依赖外部 IDE）；
- 第 11 步「修订与深化」——赛题逻辑在这里写，主路径是**任务推进**：AI 按功能拆成有序任务卡，逐卡「做这一步」实现并立即编译验证，每步过后有 AI 的下一步指引（含接线 / 上板）；任务卡上可「和 AI 商量」、可「上板反馈」、可「烧录到板子」。同一页签还有：
  - **修订**：赛题答疑（Q&A）有增补时重新分析并覆盖式重生成（可回滚）；
  - **参数速调**：扫描可调参数（阈值 / 速度 / 频率…），改一个数即自动编译验证，可恢复旧值；
  - **交付**：检查未完成步骤、打包交付物（zip 自动排除 .contest_* 内部状态文件）；
  - **新想法 / 全局商量**：单个新想法直接修正落地，或与 AI 连续讨论整体方案（讨论可转任务 / 修正 / 采纳为全局结论）；
- 第 12 步「交接提示词」（可选）：把本次生成上下文打包成一段话，复制给外部 AI。

`.contest_*` 开头的文件（如 .contest_context.json / .contest_wiring.json / .contest_tasks.json）是工具的内部状态，随生成与每次执行自动更新——请勿手动编辑。
