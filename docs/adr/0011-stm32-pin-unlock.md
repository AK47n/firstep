# ADR 0011 — stm32 引脚能力解锁：类型级 PWM + 软 I2C 参数化

- 状态：已接受（2026-08-15 grilling 定稿，用户逐轮确认；工单落 .scratch/pin-unlock-stm32/）
- 前置：ADR 0010（板级引脚配置：strict-all 实例锁的 v1 口径）

## 背景

ADR 0010 的 v1 口径把所有角色锁在"默认引脚能力 token 的实例"上（strict-all）。
用户实测发现 stm32 侧过度锁定（例：ml_mpu6050 的 I2C 只能 PB10/11），要求解锁。
三份侦察（渲染器路径 / 软 I2C 现状 / 全库硬编码扫描）把 stm32 的锁分成三类：

1. **假锁**（纯后端保守设计）：pwm 角色——motor_stm32.c 吃 `MOTOR_A_PWM_TIM/CH`
   宏、ml_pwm 支持 TIM2/3/4 全通道、渲染器已有 `_TIM/_CH` 尾形。换实例 = 宏值变化，
   零库改动。**但**骨架用 `tim_interrupt_ms_init(TIM_3, 10)`（26H 调度）/
   `TIM_2, 1`（2026C 滴答）占定时器——放宽后绑到同 TIM 实例 = 编译绿运行坏。
2. **库硬编码**（小改可解）：软 I2C——ml_i2c.h 写死 PB10/11、ml_oled.h 写死
   PB8/9，但已是宏形态、唯一消费方在库内、mpu6050 代码纯函数调用。
3. **真锁**（解 = 假绿风险）：enc 换线（`EXTI2/EXTI4_IRQHandler` 名字写死）、
   UART 换实例（`USARTx_IRQHandler` 名不联动 + TX/RX 对 + 实例冲突）、mspm0
   外设族迁移（SysConfig 外设实例固定，换外设 = 驱动代码层改动）。

## 决策

1. **stm32 pwm 角色改类型级校验**：绑定脚须有 ≥1 个 `pwm:*` token，实例由
   **绑定引脚**推导喂渲染器；mspm0 与 stm32 其余类型保持 strict-all 不变。
   分级口径 = 平台×类型。
2. **新增定时器实例冲突门禁**：扫描 main_c 骨架（clex 注释剥离后）的
   `tim_interrupt_ms_init(TIM_x)` 实例，与绑定 pwm 角色的 TIM 实例冲突 → 400
   中文。只查用户绑定（默认组合冲突不拦——现状性质，不破既有生成流）；
   识别不到不拦（漏报优于误报，宁可少拦不误伤）。
3. **软 I2C 参数化**：ml_i2c.h / ml_oled.h 的引脚宏迁入 pin_config.h（6 个宏，
   原值不变）；stm32 板定义 i2c 能力 token **去实例化**（软 I2C 参数化后实例
   无意义——总线身份在宏里不在能力 token 里），全部 io 脚加 `i2c_scl` /
   `i2c_sda`；oled manifest stm32 段补 pins 声明（OLED 一并解锁）。
4. **共享端口宏异值 400**：两条改动绑定写同一 `_GPIO/_PORT` 尾形宏且值不同
   （如 MPU6050 SCL/SDA 绑不同端口）→ 渲染层 PinBindingError。未改同族角色
   的隐式漂移仍为提示语义（前端卡片已做，工单 pin-board-config/03）。
5. **mspm0 不动**：strict-all 实例锁保留（SysConfig 真约束，ADR 0010 实证）。
6. **全解记遗留候选**（后续单独 grilling 立项）：① stm32 enc 换线（motor
   通用 EXTI handler）；② stm32 UART 换实例（ISR 名参数化 + TX/RX 对同实例
   约束 + 实例冲突检查）；③ mspm0 外设族参数化（PWMAB 换 TIMG→TIMA 等驱动
   代码层迁移，不是多改 syscfg 能解决的）。
7. **两个现状雷另立小工单**：ml_led.h 双 LED 定义并存（PA11/12 vs PC13-15，
   骨架点灯点的是 USB 脚）、startup 弱 handler `B .` 死循环（UART RX 中断
   使能但无人挂接 = 收字节即挂）。

## 后果

- "宁严勿假绿"的口径从"一律 strict-all"细化为"平台×类型分级"：能证明
  代码吃宏的类型放宽，有真硬编码的类型保持锁——严守同一个原则的两种表现。
- 验收口径 = 编译级 + 产物宏断言（UV4 0 错 + pin_config.h 宏值逐项核对）；
  运行级（电机真转 / MPU6050 真读数）留用户上板自验。
- 侦察发现的现状问题（默认值 5 组同脚冲突、fputc 写死 USART1、生成工程无
  isr.c）不入本轮，性质上属于"接线语义用户把关"的既有边界。
