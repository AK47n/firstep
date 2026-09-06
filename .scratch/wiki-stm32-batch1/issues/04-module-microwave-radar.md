# 04 — microwave_radar 微波多普勒雷达（GPIO 输入，手册 sensor--microwave-doppler-radar-sensor.md）

**要做什么：** 模块库 `microwave_radar` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼微波雷达驱动为纯驱动切片（1 × GPIO 输入），API 与 mspm0 版对齐——`microwave_radar_init()`（gpio_init 配内部上拉输入；空实现占位语义同 mspm0）+ `microwave_radar_read()`（返回 1=检测到运动/0=未检测，按 `MICROWAVE_TRIGGER_LEVEL` 极性）。

**关键事实（已取证）：**
- 页面 = **F1 标准库**：`RCC_APB2PeriphClockCmd(RCC_OUT)`、`GPIO_Mode_IPU`、`OUT_IN = GPIO_ReadInputDataBit(PORT_OUT, GPIO_OUT)`、默认宏 `RCC_OUT=GPIOA / GPIO_OUT=GPIO_Pin_1`（页面默认 PA1）、`stm32f10x.h`。
- 页面结构：bsp_radio.c/bsp_radio.h/main（3 代码块；main = `board_init()+uart1_init(115200)+while(1){printf(...)}`——剔除）。
- **极性**：mspm0 版 `MICROWAVE_TRIGGER_LEVEL 0u`（页面自一致：低=检测到——RCWL-0516 输出低有效脉冲；单宏可切）。dkx 页 IPU 上拉冗余（模块推挽输出），读数=模块实际电平；stm32 版沿用 LEVEL 0u（页面原型与 mspm0 版一致），notes 记「实物反相改宏 1」。

**换算实现**：`gpio_init(MICROWAVE_GPIO, MICROWAVE_PIN, IU)` + `gpio_get()` 按 LEVEL 宏归一；不注册中断（轮询——微波脉冲慢速）。

**引脚与默认脚（同选概率最低推理）：**
- pins：`MICROWAVE_OUT`（type `gpio_in`，default **PA4**，required true，macros `[MICROWAVE_GPIO, MICROWAVE_PIN]`）。
- pin_config.h 新宏段：`#define MICROWAVE_GPIO GPIO_A` / `#define MICROWAVE_PIN Pin_4`（注释：默认 PA4 = 叠 `MOTOR_B_ENC`（EXTI4 线，光电编码器）——微波雷达与「带编码器闭环的电机控制」不同框、同选概率最低；本件轮询不注册 EXTI，与编码器线共享正交（异口同线此时不冲突——编码器与微波同选时经绑定消解）；刻意避让声光/门禁/传感站组合件）。
- 注：页面默认 PA1（RCC_OUT=GPIOA/GPIO_Pin_1）**不采用**——PA1 已叠 adc ADC_CH1 + MOTOR_B_PWM（常备件），改 PA4（先例：mspm0 侧同理避开微波用户场景重叠）；notes 记录「页面默认脚弃用理由」。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/microwave_radar/code/microwave_radar_stm32.c/.h`（UTF-8；.c include 本模块 .h + pin_config.h + headfile.h；零引脚字面量；MICROWAVE_TRIGGER_LEVEL 0u 宏）
- [x] manifest.json platforms 增 stm32：files `[code/microwave_radar_stm32.c, code/microwave_radar_stm32.h]`、verified false、hardware_bound false、pins 如上、kit（微波多普勒套件名）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/microwave-doppler-radar-sensor.html`、notes（手册路径+原页+网盘+采购 + 极性（0u）+ 页面默认 PA1 弃用理由 + 默认脚推理 + 轮询 + 未上板）
- [x] pin_config.h 增 `MICROWAVE_GPIO/MICROWAVE_PIN`
- [x] 测试 `tests/test_module_microwave_radar.py`：形状 + 母版宏存在 + stm32 单选生成全流程 + 守卫（MICROWAVE_TRIGGER_LEVEL 0u、无 printf/main/GPIO_Init/RCC_、gpio_get 出现、无 EXTI/NVIC/IRQHandler 相关调用）
- [x] test_pins.py STM32_MACRO_VALUES 补两宏；test_default_layout.py 白名单 microwave×motor（PA4 重叠）
- [x] 编译矩阵 UV4 0/0 → verified=true
- [x] wordlist 感知传感器；词表预算链（slug 已挂接，零改动）
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；编译日志 `.scratch/wiki-stm32-batch1/matrix/microwave_radar/build.log`。
- 页面默认脚 PA1 弃用记录：PA1 已叠 adc ADC_CH1 + MOTOR_B_PWM（常备件）——默认改 PA4（叠编码器 EXTI4，微波与编码器闭环不同框；本件轮询不注册 EXTI，异口同线不冲突）。
- 宏名前缀记录：页面 RCC_OUT/PORT_OUT/GPIO_OUT/OUT_IN 无前缀撞名风险 → 统一 MICROWAVE_ 前缀；型号 mh100x vs HB100 命名不一致（wiki 自身，记录不裁决）。
- 测试：test_module_microwave_radar 7 passed；test_pins/test_default_layout 全绿（27 passed 组合跑）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
