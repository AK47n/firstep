# stm32 引脚能力解锁（PWM 类型级 + 软 I2C 参数化）——功能规格

> 2026-08-15 grilling 定稿（用户逐轮确认）。词表三词条已入 CONTEXT.md（类型级能力校验 / 定时器实例冲突 / 共享端口宏），决策已入 ADR 0011。

## 愿景

用户在板图卡上实测发现 stm32 侧"锁太死"（例：mpu6050 I2C 只能 PB10/11、电机 PWM 只能 PA0/PA1）。本轮解锁两类：**pwm 角色类型级可规划**（任意 pwm 脚，电机 PWM 换到 TIM3/TIM4 任意通道）+ **软 I2C 任意 GPIO**（mpu6050/OLED 解锁）。全解三项（enc 换线 / UART 换实例 / mspm0 外设族）记遗留候选，后续单独 grilling。

## 决策（ADR 0011 摘要）

1. stm32 pwm 改类型级校验（实例从绑定引脚推导喂渲染器）；mspm0 与其余类型 strict-all 不动。
2. 新门禁：骨架 `tim_interrupt_ms_init` 定时器实例 × 绑定 pwm 实例冲突 → 400（只查用户绑定；漏报优于误报）。
3. 软 I2C 参数化：宏迁 pin_config.h、能力 token 去实例化、oled manifest 补 pins。
4. 共享端口宏异值 400（渲染层）；未改同族角色隐式漂移仍为提示语义。
5. mspm0 不动；验收 = 编译级 + 产物宏断言，运行级用户上板自验。

## 数据契约变化

- **stm32 板定义**（boards/stm32-min-system.json）：全部 io 脚能力集加 `i2c_scl` / `i2c_sda`（无实例 token）；删除 `i2c_scl:ml_i2c` / `i2c_sda:ml_i2c` / `i2c_scl:ml_oled` / `i2c_sda:ml_oled` 四类带实例 token。pwm token 不动。
- **母版 pin_config.h**（library/masters/stm32/pin_config.h）：新增 6 宏——`I2C_GPIO GPIO_B` / `I2C_SCL_GPIO_Pin Pin_10` / `I2C_SDA_GPIO_Pin Pin_11` / `OLED_GPIO GPIO_B` / `OLED_SCL_Pin Pin_8` / `OLED_SDA_Pin Pin_9`（原值不变 = 默认路径语义不变）。
- **ml_i2c.h / ml_oled.h**：删硬编码三行，改 `#include "pin_config.h"`（guard `__PIN_CONFIG_H` 已存在；IncludePath `..` 已可达工程根）。
- **oled manifest**（library/modules/oled/manifest.json）stm32 段补 pins：OLED_SCL（i2c_scl，PB8，macros [OLED_GPIO, OLED_SCL_Pin]）/ OLED_SDA（i2c_sda，PB9，macros [OLED_GPIO, OLED_SDA_Pin]）。ml_mpu6050 manifest 不动（macros 已指向迁移目标）。
- **pwm 绑定语义**：`{"motor.MOTOR_A_PWM": "PA6"}` → ResolvedBinding.instances = ("TIM3_CH1",)（绑定引脚实例）→ pin_config.h `MOTOR_A_PWM_TIM TIM_3` / `MOTOR_A_PWM_CH TIM3_CH1 /* PA6 */`。渲染器零功能改动。

## 门禁（本轮新增两条）

| 门禁 | 位置 | 判据 |
|---|---|---|
| `_check_timer_instance_conflicts` | generator.py GENERATION_GATES（01） | main_c 注释剥离后扫 `tim_interrupt_ms_init(TIM_x`（x∈2/3/4，含 TIM_2/TIM2 两写法）× 绑定 pwm 角色实例前段 → 冲突 400 中文（errors.py 登记） |
| 共享端口宏异值 | pinwriter.py 渲染层（02） | 两条改动绑定写同一 `_GPIO/_PORT` 尾形宏且值不同 → PinBindingError 400 |

## 关键事实（侦察，实施会话必读）

- **骨架定时器占用**：2026H main.c `tim_interrupt_ms_init(TIM_3, 10)`（10ms 调度器）、2026C main.c `tim_interrupt_ms_init(TIM_2, 1)`（1ms 滴答）——sources 参考版实证，LLM 骨架同习。TIM4 暂无人用。
- **stm32 PWM 通道全集**：TIM2/3/4 × 4 通道共 12 组，每组唯一引脚（PA0/PA1/PA2/PA3、PA6/PA7/PB0/PB1、PB6/PB7/PB8/PB9）；ml_pwm 无 AFIO remap、TIM1 不可用（ml_tim 只注册 TIM_2/3/4）。PB8/9 同时是 OLED 软 I2C 默认脚、PB10/11 同时是 zigbee UART_3 + ml_i2c 默认脚——共享脚裁决靠用户（v1 语义）。
- **pin_config.h 默认值 5 组同脚冲突**（现状，不拦）：BUZZER×MOTOR_B_DIR（PB0）、DEBUG_UART×MOTOR_A_ENC/DIR（PA2/3）、LED×GRAY_D6-8（PC13-15）、DIP×GRAY_D1-4（PB12-15）、ZIGBEE×软 I2C（PB10/11）。
- **UART ISR 名不联动**（全解候选 ② 的根因）：模块只提供 `*_rx_handler()`，`USARTx_IRQHandler` 胶水在逐赛题 isr.c；生成工程无 isr.c、ml_nvic 无条件使能 RXNE → 现已是"收字节进弱 handler 死循环"的假绿（雷单 04 只修死循环，收不到数据的联动留全解）。
- **fputc 写死 USART1**（ml_uart.c:33）：printf 串流与 UWB/DIGIT/BALL_DETECT 共 TX 线——现状已知，不属本轮。
- **母版双份陷阱**：`~/.contest_generator/masters/stm32/` 是旧部署副本（无 pin_config.h、IncludePath 旧）；权威母版在仓库 `library/masters/stm32/`（config.json masters_dir 指向处）。改母版只改仓库那份。
- **ml_mpu6050 模块自带 ml_libs 子目录但不含 ml_i2c.c/h**——I2C 实现来自母版 copytree，参数化只动母版。

## 工单链

| # | 工单 | 内容 | 并行性 |
|---|---|---|---|
| 01 | `.scratch/pin-unlock-stm32/issues/01-pwm-type-level.md` | stm32 pwm 类型级 + 定时器冲突门禁 + 前端镜像 | 并行（与 03/04）——文件边界不重叠 |
| 02 | `.scratch/pin-unlock-stm32/issues/02-soft-i2c-param.md` | 软 I2C 参数化 + 共享端口宏门禁 | **串行**（01 合 main 后——test_pin_bindings.py 同缝） |
| 03 | `.scratch/pin-unlock-stm32/issues/03-ml-led-dual-def.md` | ml_led.h 双 LED 修复（现状雷） | 并行 |
| 04 | `.scratch/pin-unlock-stm32/issues/04-startup-weak-handler.md` | startup 弱 handler 死循环修复（现状雷） | 并行 |

同缝提示：`.scratch/index-html-ui-redo/issues/01`（文字 UI 美化）也动 index.html——01 工单先行（功能优先），redo 其后 rebase（其提示词已含 rebase 铁律）；8000 端口单实例，多会话真机验证请错峰。

## 全解遗留候选（后续单独 grilling 立项）

1. **stm32 enc 换线**：motor 模块 `EXTI2/EXTI4_IRQHandler` 名字写死（换线 = 编译过中断不触发）——解法候选：模块改通用 handler（`EXTI9_5_IRQn` 共线问题一并）或生成器按绑定注入 handler 名。
2. **stm32 UART 换实例**：ISR 名参数化 + TX/RX 对同实例约束 + 跨模块实例冲突检查（UART_2 被 debug_uart 占等）。
3. **mspm0 外设族参数化**：PWMAB 换 TIMG→TIMA 等外设级迁移——动 `DL_TimerG_*` 驱动调用层，syscfg 改写器只管 $assign 的下一层能力。
