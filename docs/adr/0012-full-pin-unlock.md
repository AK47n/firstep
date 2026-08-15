# ADR 0012 — 引脚全解：enc 换线 + UART 换实例 + mspm0 实例迁移分级

- 状态：已接受（2026-08-15 grilling 定稿，用户逐轮确认并按推荐落盘；工单落 .scratch/pin-full-unlock/）
- 前置：ADR 0010（板级引脚配置 v1 口径）、ADR 0011（pwm 类型级 + 软 I2C 参数化）

## 背景

ADR 0011 解了 stm32 pwm 类型级与软 I2C，三类"真锁"记遗留：① enc 换线（EXTI handler
名写死）、② UART 换实例（ISR 名不联动 + TX/RX 对 + 实例冲突 + fputc 写死 USART1）、
③ mspm0 外设族参数化（模块代码写死 DL_TimerG 族 API）。用户定调：**只有两平台每个
可用引脚都能配置才是合适的配置功能**。双侦察（stm32 剩余锁清单 / mspm0 引脚系统全量）
补齐事实后 grilling 定稿。

## 决策

1. **全解定义 = 角色级全解 + 引脚级覆盖**：每个角色引脚在其电气能力集内自由绑定，
   代码不再写死脚/实例；每个物理排针脚至少被一种角色选用。物理不可用脚继续灰显：
   SWD（stm32 PA13/14 在板缘 4P 弯针、不在 2×20——用户标准：独立弯针上的锁；mspm0
   PA19/20 同）、晶振、CH340E（PA10/11）、VREF-（PA21）、BOOT1（PB2 未引出）。
2. **stm32 enc 类型级化**：绑定脚须有 enc token；线号随绑定推导喂 _LINE 宏渲染
   （尾形已有，渲染器零改动）。motor_stm32.c 重构为 7 个条件 handler（EXTI0-4 /
   EXTI9_5 / EXTI15_10，按 _LINE 宏预处理器选择，共线组内 PR 位分派 A/B 编码器）。
   ml_exti 枚举 24→48 项（PA/PB/PC × 线 0-15）+ NVIC 通道公式（线 5-9 → EXTI9_5_IRQn、
   10-15 → EXTI15_10_IRQn）。板定义 exti/enc token 扩线 8-15。
3. **EXTI 线冲突门禁**：两绑定 exti/enc 角色线号（脚号 mod 16）相同且引脚不同 →
   400（异口同线互斥，编译绿运行坏）；同脚共享仍提示语义。
4. **stm32 UART 类型级化**：TX/RX 对同实例约束（两脚 uart token 实例集交集非空，
   空 = 400 提示成对绑定）；实例冲突门禁——绑定推导实例 × 未绑定角色默认实例 → 400，
   绑定×绑定同实例放行（共享提示语义，换位操作合法），默认×默认不查（UWB/DIGIT/
   BALL 共 UART_1 现状合法，与 TIM 门禁同"只查用户绑定"口径）；ml_uart 增
   uart_pin_init_ex（引脚宏化，旧函数保留）；**fputc 跟随 DEBUG_UART**（默认 printf
   流从 USART1/PA9 挪到 USART2/PA2——默认行为变化，用户已确认）；**母版静态 isr.c +
   pin_config.h 渲染 USARTx_IRQ_CALLS 聚合宏**（按绑定实例分组各模块 rx_handler
   调用，__weak 空兜底——纯静态 isr.c 会被默认共享实例的重复定义炸掉，审视修正）。
5. **mspm0 实例迁移分级**：
   - **同族迁移**（UART0↔UART1、I2C0↔I2C1、TIMGx↔TIMGy、GPIO 组换端口）——改写器
     改 peripheral/port 字段，实例名不动 → SysConfig 生成宏名不动 → 模块代码零改动
     （step_motor 四脚同端口锁借此解）；
   - **跨族迁移**（TIMG↔TIMA）——API 函数族变，模块 #if 双分支 + 生成器渲染族标志头
     pin_family.h（pin_config 哲学的 mspm0 版）；
   - step_motor 跨族物理不可能（DCC_100_PWM2 需 32 位，TIMA 16 位）→ 其引脚解锁靠
     同族迁移（TIMG12 可达脚 PA14/PB20）。
6. **mspm0 pwm 门禁分级**：Tier A 后同族内类型级（推导实例族 == 默认实例族）；Tier B
   后全类型级（跨族放开）+ PWMAB 两通道同实例门禁。mspm0 同脚撞车由 SysConfig
   Resource conflict 自然拦（已实证），不另设门。
7. **默认 5 组同脚冲突重排**：改 manifest 默认 pins + pin_config.h 母版默认值，目标
   冲突归零（物理不可达则最小化并明示）；放主链最后（机制稳定后重排数据，全量默认
   回归）。
8. **包型号悬案**：纳入并行前置（既有工单 .scratch/mspm0-board-package/issues/01，
   用户物理看丝印），不阻塞主链。
9. **验收口径**：编译级 + 产物断言（UV4/gmake 0 错 + pin_config.h 宏值 / isr.c 聚合 /
   syscfg 字段逐项核对）+ 红证先行；运行级用户上板自验（ADR 0011 口径延续）。

## 后果

- "宁严勿假绿"口径从"平台×类型分级"细化为"平台×类型×族"三级。
- 默认 printf 流位置变化（USART1→USART2），真机验收需注意串口观察位置。
- 默认重排会改变已验收的默认产物形态（需按新基线重验收）。
- 冲突仲裁面完整化：引脚共享 = 提示语义；实例/线级 = 400；mspm0 同脚 = SysConfig 拦。
- Tier B 存在数据风险：TIMA 通道在排针的分布未全表——若 TIMA 实例无 C0+C1 同实例
  排针对，motor 跨族物理不可达，则该类 pwm 脚的能力标注退回"无消费方实例"灰显
  （引脚级覆盖让位于物理现实），工单 04 第一步 = 数据裁决。
