# 引脚全解（enc 换线 + UART 换实例 + mspm0 实例迁移分级）——功能规格

> 2026-08-15 grilling 定稿（用户逐轮确认 + "按你的推荐来"）。词表三词条已入 CONTEXT.md（EXTI 线冲突与共线组 / UART 实例仲裁 / mspm0 实例迁移分级），决策已入 ADR 0012。

## 愿景

用户在板图卡上实测发现"锁太死"后定调：**只有两平台每个可用引脚都能配置才是合适的配置功能**。本轮把 ADR 0011 遗留的三把真锁全部拆除——stm32 enc 换线（EXTI handler 名写死）、stm32 UART 换实例（ISR 名不联动 + fputc 写死 USART1）、mspm0 外设族参数化（模块写死 DL_TimerG 族）；并顺手把 stm32 默认 5 组同脚冲突重排归零。全解定义 = 角色级全解 + 引脚级覆盖（物理不可用脚——SWD/晶振/CH340E/VREF-/BOOT1——继续灰显）。

## 决策（ADR 0012 摘要）

1. 全解 = 角色级全解 + 引脚级覆盖；SWD（PA13/14 在板缘 4P 弯针、mspm0 PA19/20）维持灰显（用户标准）。
2. enc 类型级：绑定脚须有 enc token，线号随绑定推导喂 _LINE 宏；motor 7 条件 handler（_LINE 宏预处理器选择 + 共线组 PR 分派）；ml_exti 枚举 48 项 + NVIC 通道公式；板定义 exti/enc token 扩线 8-15。
3. EXTI 线冲突门禁：异口同线 400。
4. UART 类型级：TX/RX 对交集非空（空 = 400 成对绑定）；实例冲突门禁 = 绑定实例 × 未绑定角色默认实例 → 400（绑定×绑定放行 = 换位合法；默认×默认不查 = UWB/DIGIT/BALL 共 UART_1 现状合法）；fputc 跟随 DEBUG_UART；母版静态 isr.c + USARTx_IRQ_CALLS 聚合宏入 pin_config.h 渲染面。
5. mspm0 迁移分级：同族（改 peripheral/port 字段，模块零改动）/ 跨族（模块 #if 双分支 + pin_family.h 渲染）；step_motor 跨族物理不可能。
6. mspm0 pwm 门禁分级：同族类型级 → 全类型级 + 两通道同实例门禁。
7. 默认 5 组同脚冲突重排（数据工单，主链最后）。
8. 包型号悬案并行前置（.scratch/mspm0-board-package/issues/01）。
9. 验收 = 编译级 + 产物断言 + 红证先行；运行级上板自验。

## 数据契约变化

- **stm32 板定义**（boards/stm32-min-system.json）：PA8-15 / PB8-15 / PC13-15 加 `exti:PAx` / `exti:PBx` / `exti:PCx` token 与对应 `enc:8..15` 线号 token；既有 token 不动（01）。
- **stm32 manifests**（01/02/05）：
  - motor：enc 角色 default 不动（PA2/PA4）；换线后由类型级校验接管。
  - digit_uart / ball_detect / debug_uart / uwb_uart / zigbee_uart / zigbee_uart_key：RX 条目补 macros `[_RX_GPIO, _RX_Pin]`（TX 条目已有 [_UART, _INST]）；TX 条目另补 `[_TX_GPIO, _TX_Pin]`（02）。
- **pin_config.h**（母版，02）：每 UART 角色 +4 宏（TX_GPIO / TX_Pin / RX_GPIO / RX_Pin，原值 = 现 switch 表引脚）；+3 聚合宏 `USART1_IRQ_CALLS`（digit + ball + uwb 默认序）/ `USART2_IRQ_CALLS`（debug）/ `USART3_IRQ_CALLS`（zigbee）——渲染器按绑定重分组；渲染尾形 +`_IRQ_CALLS` / `_TX_GPIO` / `_TX_Pin` / `_RX_GPIO` / `_RX_Pin`。
- **isr.c**（母版新增，02）：5 个 `__weak void *_rx_handler(void){}` 兜底 + 3 个 `USARTx_IRQHandler`（体 = 调 `USARTx_IRQ_CALLS`）。uvprojx 确定性渲染器文件树全 .c 引用 → 自动纳入（验证）。
- **ml_uart.c**（02）：fputc 改 `DEBUG_UART_INST->SR/DR`（include pin_config.h）；新增 `uart_pin_init_ex(uart_n, tx_gpio, tx_pin, rx_gpio, rx_pin)`（RCC/NVIC 公式沿用），旧 `uart_pin_init` 保留。
- **ml_exti.c**（01）：枚举 24→48 项（PA/PB/PC × 线 0-15）；NVIC 通道公式（线 ≤4 → EXTI0-4_IRQn、5-9 → EXTI9_5_IRQn、10-15 → EXTI15_10_IRQn）。
- **mspm0.syscfg 改写面**（03/04）：pinwriter 支持改 `peripheral` 字段（uart/i2c/pwm，实例名/宏名/通道名不动）；GPIO 组零 `port` 改动——SysConfig 由组内引脚 $assign 自动推导组端口（03 前置验证实证）。**无 pin_family.h**：模块代码全程用 SDK 通用 `DL_Timer_*` API（`DL_TimerA_*`/`DL_TimerG_*` 只是重定向宏），跨族零模块改动（04 真机实证）。

## 门禁（本轮新增四条）

| 门禁 | 位置 | 判据 |
|---|---|---|
| `_check_exti_line_conflicts` | generator.py GENERATION_GATES（01） | 绑定 enc/exti 角色两两：线号（脚号 mod 16）相同 ∧ 引脚不同 → 400 中文（errors.py 登记） |
| `_check_uart_instance_conflicts` | generator.py GENERATION_GATES（02） | 绑定 UART 角色推导实例 × 未绑定 UART 角色默认实例 → 400；绑定×绑定 / 默认×默认不查 |
| mspm0 同端口组约束 | pin_bindings.py（03） | step_motor 四脚绑定 port 不一致 → 400 |
| PWMAB 两通道同实例 | pin_bindings.py（04） | C0/C1 推导实例不同 → 400 |

## 关键事实（侦察，实施会话必读）

- **EXTI 线 = 脚号 mod 16**：PA2/PB2 同线互斥；线 5-9 共 EXTI9_5_IRQHandler、10-15 共 EXTI15_10_IRQHandler。motor_stm32.c 现为 EXTI2_IRQHandler(:50)/EXTI4_IRQHandler(:62) 两个独立 handler，体内用 `MOTOR_A/B_ENC_LINE` 宏清 PR。ml_exti 枚举现仅 PA0-7/PB0-7/PC0-7（24 项，:13-36），NVIC 现公式线 5-7 → EXTI9_5_IRQn（:68-71）。
- **UART 现状**：ml_uart.c uart_pin_init switch 表（UART_1→PA9/PA10、UART_2→PA2/PA3、UART_3→PB10/PB11，:52-63）、RCC 使能公式（:101-104）、NVIC 通道 uartn+37（:109）；**fputc 写死 USART1（:31-36）**——printf 现与 UWB/DIGIT/BALL_DETECT 共 TX 线；模块只提供 `*_rx_handler()`（digit_uart.c:81 / ball_detect_stm32.c:83 / debug_uart.c:38 / uwb_uart.c:148 / zigbee_uart.c:40），**生成工程无 isr.c** = UART 收字节进弱 handler 的假绿（04 雷单只修了死循环）。
- **UART 实例默认布局**：DIGIT=UART_1、BALL=UART_1、UWB=UART_1（三角色共享，现状合法）、DEBUG=UART_2、ZIGBEE=UART_3；板定义 uart token 仅 UART_1（PA9/10）、UART_2（PA2/3）、UART_3（PB10/11）。**用户绑任何单角色换实例必撞某默认角色 → 400；合法换位需多角色同时绑**（真机场景用三组绑定全换位验证）。
- **stm32 引脚字面量已清零**：模块代码零 Pin_x/GPIO_x 字面量（grep 只命中注释），全走 pin_config.h 宏——换脚机制已就绪，剩 ml_libs 三张 switch 表（uart/exti）+ fputc。
- **mspm0 syscfg 实例表**（mspm0.syscfg）：PWMAB=TIMG0（C0=PA12/C1=PA13）、DCC_100_PWM2=TIMG12（C0=PA14，clockPrescale 必须 1，32 位直算周期）、MOTOR_PID=TIMG6（无引脚）、NTB=TIMG7（无引脚）、DC_MOTOR=GPIO 8 脚（跨 PA/PB）、HUIDU=GPIO 8 脚（R3/R4=PB6/PB7 排针板内，huidu-r34-default 工单）、KEY=PA2、LED_BEEP=PA15、STEP_MOTOR=GPIOB 4 脚（同端口硬约束；SLP2/DIR2=PB4/PB5 排针外让位）、IMU601=UART0（PA28/31）、DIGIT_UART=UART1（PA8/9）、OLED=I2C1（PB3/PB2）、I2C_0=I2C0（PA0/PA1）。
- **mspm0 模块族写死表（04 实证修正：不存在"写死族"问题）**：motor.c `DL_Timer_setCaptureCompareValue(PWMAB_INST,…)`(:50/56) + startCounter(:58-59) 等全部走 SDK **通用 `DL_Timer_*`**；`DL_TimerA_*`/`DL_TimerG_*` 在 dl_timera.h/dl_timerg.h 只是重定向宏——跨族换 peripheral 零模块改动（04 真机 clean all 0 错）。step_motor.c `DCC_100_PWM2_INST`(:9 等) + IRQ `DCC_100_PWM2_INST_IRQHandler`(:67)；mpu_port.c `I2C_0_INST`；imu.c `IMU601_INST`；oled.c `OLED_INST`；digit_uart_mspm0.c / ball_detect.c `DIGIT_UART_INST`。
- **改写器硬限制**（pinwriter.py）：只匹配 `$assign` 行（_SYSCFG_ASSIGN_RE）；rewrite_syscfg 槽位定位 = 默认引脚值唯一；实例名/宏名/通道名/其余行逐字节不动；不能增删实例。peripheral 改写面已由 03/04 实施并真机验证。
- **排针 31/31 可用脚全被默认布局占用**（33 个 $assign，含排针外 PB4/PB5）——mspm0 单角色换脚必撞已占用脚（SysConfig Resource conflict 自然拦，已实证）；换位改法先例（pin-board-config 02/03）。**syscfg-prune/01 起生成按选中模块裁剪 syscfg：未选模块实例不落盘，其引脚空出可绑（默认布局 = 理论上限）。**
- **TIMA 通道排针分布已全表（04 数据裁决）**：TIMA0 C0+C1 对 = PA0/PA1、PA8/PA9、PB8/PB9；TIMA1 C0+C1 对 = PA15/PA16、PA17/PA18、PB2/PB3、PA28/PA31——跨族物理可达（sysconfig_cli + gmake 0 错实证）。
- **默认 5 组同脚冲突已重排 4 组**（工单 05）：BUZZER→PA15、MOTOR_A_ENC/DIR→PB5/PB4、GRAY_D6-8→PB3/PB6/PB7、软 I2C→PA11/PA12；**DIP×GRAY_D1-4（PB12-15）为唯一残留**（全库 42 角色 vs 排针 32 脚，数学上无法全互异——保留并白名单，见 tests/test_default_layout.py）。
- **骨架 TIM 占用**：2026H `tim_interrupt_ms_init(TIM_3, 10)`、2026C `TIM_2, 1`（TIM 冲突门禁已拦用户绑定）。
- **母版双份陷阱**：`~/.contest_generator/masters/stm32/` 是旧部署副本，改母版只改仓库 `library/masters/`。
- **真机惯例**：worktree 零写入启动法（AppContext 内存 replace 指 worktree 库目录 + GENERATE_CHECK_CACHE_DIR 复用主检出缓存 + --clarify 20 条零警告）；UV4 `-r` 全量重建；8000 端口单实例错峰。

## 工单链

| # | 工单 | 内容 | 并行性 |
|---|---|---|---|
| 01 | issues/01-enc-reline.md | stm32 enc 类型级 + EXTI 线冲突门禁 + motor 条件 handler + ml_exti 扩 + 板定义数据 + 前端镜像 | 链首 |
| 02 | issues/02-uart-reinstance.md | stm32 UART 类型级 + TX/RX 对 + 实例冲突门禁 + isr.c + fputc + ml_uart 参数化 + 前端镜像 | 串行（01 后，pin_bindings/pinwriter/tests 同缝） |
| 03 | issues/03-mspm0-same-family.md | mspm0 Tier A 同族迁移（改写器 peripheral/port 字段 + 同族类型级 + GPIO 组换端口） | 串行（02 后） |
| 04 | issues/04-mspm0-cross-family.md | mspm0 Tier B 跨族（数据裁决先行 + motor 双分支 + pin_family.h 渲染 + 全类型级 + 两通道门禁） | 串行（03 后） |
| 05 | issues/05-default-conflicts.md | stm32 默认 5 组同脚冲突重排（数据工单 + 全量默认回归） | 串行（04 后） |
| 前置 | .scratch/mspm0-board-package/issues/01（既有） | 包型号核实 + HUIDU R3/R4 裁决（用户物理看丝印） | 并行独立 |

全串行理由：pin_bindings.py（类型级分支）/ pinwriter.py / tests/test_pin_bindings.py / index.html（pinCanHost）/ 板定义五同缝；05 的默认值变更会改 01-04 测试预期（test_pins 宏值表）。同缝提示：`.scratch/index-html-ui-redo/issues/01` 也动 index.html——本链先行（功能优先），redo 其后 rebase（其提示词已含 rebase 铁律）；8000 端口单实例错峰。

## 遗留（本轮不做）

- stm32 PWM 12 组固定通道不动（ml_pwm 无 AFIO remap、TIM1 不可用——ml_tim 只注册 TIM_2/3/4）。
- ADC 换通道/多通道、SPI 硬实例——strict-all 保持（无消费方驱动解锁）。
- step_motor stepper_id==2 单路硬编码——已知现状。
- TSV 重定义列（ml_libs 未实现）仍不进 token。
- 深度引脚仲裁（分时共享的静态分析）——维持提示语义（v1 口径）。
