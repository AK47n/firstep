# 侦察 03：人机与执行三件（joystick / servo / relay）

> 2026-09-25，只读侦察（未新建、未修改任何文件）。全部结论带 `file:line`。
> 用途：`library/hwcheck_recipes.json` 写配方时的事实底稿。
> 由并行侦察子代理产出，原文照录。

## 0. 「配方能写哪些名字」的判据面（先看这节，它决定下面每一格怎么写）

- 校验器 `src/contest_generator/hwcheck_recipe.py:791-927`（`validate_recipes`）：
  - `init`/`probe` 只查**调用名**（标识符紧跟 `(`，`_calls_in` :586-606）；
  - `read` 表达式**整条**过判据——所有裸名字（宏/常量也算）都必须在清单里（:892-901）；
    读数出口是 `hwcheck_report_int(int)`（`hwcheck.py:1239`）→ 只能整数；
    标签 = 表达式前 60 字符（:1322-1323），**表达式要短**；
  - `include` 判据面 = 该平台「库内所有模块该平台条目的 .h 基名 ∪ 母版树的 .h 基名」
    （`platform_header_names` :369-396）。
- 清单装配 `interface_names`（:1040-1117）= 模块自己 .h ∪ **母版头** ∪ 对象宏 ∪ extern 全局量 ∪ enum/typedef 名。
- ⚠ **mspm0 母版没有任何 .h**（`library/masters/mspm0/` 只有 main.c / mspm0.syscfg / .project /
  .cproject / targetConfigs）→ mspm0 侧配方只能引用**模块自己 .h 里的名字**。SysConfig 生成宏
  （`JOYSTICK_PORT` / `JOYSTICK_SW_PIN` / `ADC12_0_ADCMEM_1` / `RELAY_PORT` /
  `RELAY_RELAY_OUT_PIN` / `SERVO_PWM_INST` / `SERVO_PWM_INST_CLK_FREQ` / `GPIO_SERVO_PWM_C0_IDX`）
  和 driverlib（`DL_GPIO_readPins` / `DL_Timer_setLoadValue`）**一律不能出现在配方任何段**（含 include）
  → 校验期红。stm32 侧相反，母版头（`pin_config.h` / `ml_*.h` / `headfile.h`）里的名字全部可用。
- stm32 框架自动 include：`headfile.h`（聚合 ml_gpio/ml_adc/ml_pwm/ml_delay… `ml_libs/headfile.h:1-17`）
  恒在；`pin_config.h` **只在通用总线扫描时才自动进**（`hwcheck.py:824-825,845-848`）→ 配方要引用
  `RELAY_GPIO` / `JOYSTICK_X_CH` 必须自己写进 `include.headers`（先例：beep stm32 配方
  `library/hwcheck_recipes.json:396-397`）。
- mspm0 框架自动 include：`ti_msp_dl_config.h` + 按需 `debug_uart_mspm0.h`/`oled.h`/`delay.h`/`led.h`
  （`hwcheck.py:210-218`）；SysConfig 初始化 `SYSCFG_DL_init()` 是活代码（:231-233）。
- 生成期还有第二道 include 解析门（`generator.py:1541-1595`，判据面 = 本次语料里的模块目录 ∪
  母版根头 ∪ 搜索目录）：**引用别的器件模块的头，配方校验能过、但那次没选那件就编不过**；
  三件 manifest 的 `dependencies` 都是 `[]`，不会自动带。
- console 字符：保留 `r/y/g/o/b` + `?`（`hwcheck_console.py:99-110`）；单字符、大小写不敏感、
  两件撞车即红（:573-650）。现有 10 格已占 `a d j k l m p s u x` → 剩余字母
  `c e f h i n q t v w z`（数字 0-9 也全空）。
- 三件的 `init` 全是 **void**，`probe` 都**没有**可判的身份寄存器 → 都会落进「未判定」档，
  渲染器固定加一句通用话术「本件没有可读的身份 / 状态寄存器…（灯闪 / 屏亮）」
  （`hwcheck_recipe.py:1303-1319`）——note 里必须像 sr04 那样把这句翻译成本件的现象
  （看读数 / 听咔哒 / 看舵机臂）。

---

## 1. joystick

### 1.1 mspm0

- **include**：`["joystick.h"]`（`library/modules/joystick/manifest.json:7-10`；`joystick_stm32.h`
  在 mspm0 侧会过不了 include 判据）。
- **prereq**：空。SysConfig 已经把 ADC12_0 + JOYSTICK 实例配好
  （`mspm0.syscfg:124,756-761,1288-1313`），`SYSCFG_DL_init()` 框架已调；`joystick_init()` 只
  `DL_ADC12_enableConversions()`（`code/joystick.c:36-41`）。
- **init**：`joystick_init()` → **void**（`code/joystick.h:26`）→ **不写 `init_expect`**。
- **probe**：**没有**。理由 = 没有身份/状态寄存器；唯一数字量 SW 是"人按才有意义"的输入
  （与 key 同款，`hwcheck_recipes.json:344` 的口径）。**能自证到哪一层**：X/Y 两轴是真实 ADC 测量
  （12bit 4 次平均）、SW 是真实引脚读 → 板上**能证"模拟通路 + 按键通路都在动"**，
  但**没有任何恒等于某值的量**可作 OK/FAIL 判据。
  - 可选但不推荐：`probe: {calls:["joystick_read_sw()"], expect:"0"}`（松手=0 的静态电平）
    —— 学生一上手就按着（或接线把 SW 拉低）就假 FAIL；建议照 key 的先例**不写探头**。
- **read**（建议 3 条 + 可选 1 条；`joystick_read_*_percent()` 返回 `uint16_t`，天然整数）：

  | expression | unit（正常范围/现象） |
  |---|---|
  | `joystick_read_x_percent()` | `X 轴 0-100%（不推杆≈50；推到左右两端应接近 0 / 100）` |
  | `joystick_read_y_percent()` | `Y 轴 0-100%（不推杆≈50；推到上下两端应接近 0 / 100）` |
  | `joystick_read_sw()` | `摇杆帽按键：1=按下 / 0=松开（按住应看到 1）` |
  | 可选 `joystick_read_x()` | `X 轴 12bit 原始值 0-4095（中点理论 ≈2048）` |

  ⚠ **中点 50% 是"页面/厂商口径的理论值"，库内明确写着没实测**：mspm0 条目"**未上板**"
  （`manifest.json:13`）；stm32 条目"**未上板（中心值/死区真机校准留后续）**"（`manifest.json:44`）
  + `tests/test_module_joystick.py:199` 直接断言 `"未上板"`。note 只能写"应≈50、允许偏差、要实测"。
  ⚠ 本平台两个百分比宏**不在头文件里**（`JOYSTICK_ADC_MAX`/`JOYSTICK_ADC_SAMPLES` 定义在
  `code/joystick.c:16-18`）→ 不能写进 mspm0 的 read；stm32 侧它们在 `joystick_stm32.h:31,35`。
- **console**：建议 `t`（备选 `i`、`c`）。说明示例：`摇杆：重读 X/Y 百分比与按键状态（推一下摇杆看数字变）`。
- **note 要点**：
  1. 默认脚：X=**PA26**（ADC12_0 **MEM1**/CHAN_1）、Y=**PA25**（**MEM2**/CHAN_2）、SW=**PA9**
     （gpio_in，SysConfig 配 `internalResistor = PULL_UP`，`mspm0.syscfg:756-761`；低有效）。
  2. **ADC12_0 是 8 槽 sequence**（MEM0=PA24 归 adc、MEM1=PA26 X、MEM2=PA25 Y、MEM3=PA27 归
     ir_distance、MEM4=PB20 mq135、MEM5=PB24 mq5、MEM6=PA22 flame、MEM7=PA14 soil；
     startAdd=0 / endAdd=7，**槽位 8/8 用满**）。与 **adc 模块共享实例**：adc 默认读 MEM0（PA24），
     joystick 读 MEM1/MEM2 → 不同槽位、顺序调用互不干扰；但 adc 的 `ADC_Channel_1` **就是
     joystick X 的 PA26**（同一条物理通道）。
  3. 同脚：PA26 还与 zigbee_uart/zigbee_link/zigbee_uart_key TX、as32 TX、huidu R1、xunji P4、
     pid GRAY_D5、ttp224 OUT3、nrf24l01 CLK、ir_remote OUT 重叠；PA25 同 RX 族 + huidu L4 +
     xunji P6 + pid GRAY_D4 + ttp224 OUT2 + nrf24l01 MOSI；PA9 叠 digit_uart/coord_detect/open_mv4 RX、
     mlx90614 SCL、nrf24l01 MISO、tp_xpt2046 DIN。**同一物理脚只能接一件器件**。
  4. **读数可能恒 0 的坑**（见 §4-D2）：不要把"读到 0"直接读成"杆推到端点"。
  5. 平台差异一句话：mspm0 = MEM1/MEM2（PA26/PA25）+ PA9；stm32 = ADC_Channel_1/0（PA1/PA0）+ PA10
     ——**引脚完全不同，Y 的通道号也不同（2 vs 0）**。

### 1.2 stm32

- **include**：`["joystick_stm32.h"]`；若要用 `JOYSTICK_X_CH`/`JOYSTICK_SW_GPIO` 等宏，再加
  `"pin_config.h"`（`headfile.h` 不带它）。
- **prereq**：空。`joystick_init()` 内部自己 `adc_init(ADC_1, JOYSTICK_X_CH)` / `…Y_CH`
  （`code/joystick_stm32.c:38-45`），ml_adc 的 adc_init 内含 AIN 引脚 + APB2 时钟 + 6 分频 + 复位校准。
- **init**：`joystick_init()` → **void**（`joystick_stm32.h:44`）→ 不写 `init_expect`。
- **probe**：**没有**，理由同上。
- **read**：同 mspm0 三条；
  - 可选 `JOYSTICK_ADC_MAX`（4095）/`JOYSTICK_ADC_SAMPLES`（4）——能写，但不如直接给原始值。
- **console**：同 `t`。
- **note 要点**：
  1. 默认脚：X=**PA1**（`JOYSTICK_X_CH = ADC_Channel_1`）、Y=**PA0**（`ADC_Channel_0`）、
     SW=**PA10**（`pin_config.h:205-208`，`tests/test_module_joystick.py:184-187,209-212` 守卫）。
  2. **与 adc 模块共用 ADC1 通道**：adc 配方读的 `ADC_0_CH/ADC_1_CH` = CH0/CH1 = PA0/PA1
     ——与 joystick Y/X **是同一对物理脚**（与 mspm0 的"不同 MEM 槽"不同）。顺序调用不串。
  3. PA0/PA1 **同时是 motor 的 PWM 主脚**（`MOTOR_A_PWM=TIM2_CH1/PA0`、`MOTOR_B_PWM=TIM2_CH2/PA1`）；
     PA10 与 10 件共享。`tests/test_default_layout.py:139-140` 是权威占用表。
  4. 采样口径：4 次快平均（`JOYSTICK_ADC_SAMPLES 4u`）；`adc_get` 无显式超时（母版实现），
     与 mspm0 的"50 次自旋超时"不同口径。
  5. 中点同样**未实测**。

---

## 2. servo

### 2.1 两平台共同（只有一个头 `servo.h`）

- **include**：`["servo.h"]`（**两平台同一头**；stm32 条目没有 `servo_stm32.h`）。
- **函数（两平台同名同型，`code/servo.h:37-38`）**：
  - `void servo_init(uint8_t servo_id, uint8_t channel);` ← **双参！**
  - `void servo_set_angle(uint8_t servo_id, uint16_t angle);`（越界钳到 `SERVO_ANGLE_MAX`=180）
- **init**：`servo_init(0, 0)` → **void** → 不写 `init_expect`。
- **prereq**：空（stm32 走母版 ml_pwm；mspm0 走 SysConfig 的 SERVO_PWM 实例）。
- **probe**：**没有**。纯写执行件：驱动无读回接口，定时器/比较寄存器也不是身份寄存器。
  **能自证到 = 只能证"调用没崩、PWM 配置写下去了"**，舵机转没转只有**眼睛看舵机臂**。
  所以 `probe` 只能放**不带 expect 的动作**（照 xunji/sr04 先例）。
  推荐动作：`servo_set_angle(0, 0)` → `delay_ms(600)` → `servo_set_angle(0, 90)` → `delay_ms(600)`
  → `servo_set_angle(0, 180)` → `delay_ms(600)` → `servo_set_angle(0, 90)`。
  ⚠ **mspm0 上先别扫到 180°**（§4-D1）→ mspm0 侧建议扫 `0 → 90 → 0`。
- **read**（两平台都只能用 `servo.h` 的常量）：

  | expression | unit |
  |---|---|
  | `SERVO_ANGLE_MAX` | `角度满量程（180°；越界自动钳到端点）` |
  | `SERVO_FREQ_HZ` | `控制频率 50Hz（周期 20ms）` |
  | `SERVO_PULSE_US(90)` | `中位脉宽 µs（500=0°/1500=90°/2500=180°）` |

  这三条都是"驱动的换算表回显"，**不是测量值**——note 必须说清"它证的是换算常量，不证舵机转了"。
- **console**：建议 `v`（serVo）。说明：`舵机：重跑 0°→90°→0° 扫一遍（盯着舵机臂动不动）`。
- **note 要点（平台差异）**：
  - **stm32**：`SERVO_PWM_TIM = TIM_4`、`SERVO_PWM_CH = TIM4_CH1`（**PB6**，`pin_config.h:28-30`）。
    `pwm_init` 设 `ARR = 1000000/fre-1 = 19999`、`PSC=71` → 1MHz 计数 → **20ms 周期**；
    `MAX_DUTY=50000`，0/90/180° = **1250/3750/6250** 计数 = 0.5/1.5/2.5ms。
  - **mspm0**：SysConfig 实例 `SERVO_PWM` → **TIMG8 C0 = PA7**（`mspm0.syscfg:104-111`）；
    周期在运行时按 `SERVO_PWM_INST_CLK_FREQ` 算。
  - **上电瞬间现象**：SysConfig 生成的 SERVO_PWM 初值 `.period = 65535`、`.startTimer = STOP`
    → 上电**不出脉冲**；`servo_init()` 一跑就配 0° 并启动 → **舵机臂会猛地转到 0° 位置**，
    这是正常现象。
  - **撞脚**：stm32 **PB6** 还与 pid GRAY_D7、rc522 SCK、lcd/oled SPI DC 等重叠；
    mspm0 **PA7** 与 motor BIN2、ds18b20 DATA、rc522 CS 重叠。
  - **上板状态**：只有编译证据。

---

## 3. relay

### 3.1 mspm0

- **include**：`["relay.h"]`；**prereq**：空。
- **init**：`relay_init()` → **void**（`relay.h:44`；实现只 `relay_set(0)`）→ 不写 `init_expect`。
- **接口名**：**只有 `relay_init()` 和 `relay_set(uint8_t state)`**（`relay.h:44,50`）——**没有**
  `relay_on`/`relay_off`/`relay_toggle`；语义 `1=吸合 / 0=断开`；**没有通道宏**（单路）。
  极性宏 `RELAY_ON_LEVEL = 0u`（低电平吸合，`relay.h:40`）。
- **probe**：**没有**（纯写执行件；mspm0 侧连引脚都读不了）。只能放动作：
  `relay_set(1)` → `delay_ms(500)` → `relay_set(0)`。
- **read**：**只有 1 条诚实的**：`RELAY_ON_LEVEL`。**不要**硬凑 `DL_GPIO_readPins(...)`（校验期红）。
- **console**：建议 `e`（`r` 是保留字）。
- **note 要点**：
  1. 默认 OUT = **PA1**（`mspm0.syscfg:743-749`：`initialValue = SET`）→ 生成宏
     `RELAY_PORT`/`RELAY_RELAY_OUT_PIN`（配方里不能写）。
  2. **上电瞬间不吸合**（syscfg 初值 = 断开 + `relay_init` 亦置断开，双保险）→ 这块板上**不会**
     听到上电咔哒。
  3. 撞脚：**PA1** 与 ml_mpu6050 的 I2C_0 SCL、i2c_probe SCL、gp2y1014au LED 重叠。
  4. 负载侧：模块 5V 供电、光耦隔离、可控 250V/10A AC + 30V/10A DC；**继电器是感性负载**——
     接高压/市电负载前先断开或空载测。
  5. 上板状态：manifest 末句"**未上板**"。

### 3.2 stm32

- **include**：`["relay_stm32.h", "pin_config.h"]`（要读 `RELAY_GPIO`/`RELAY_PIN`，`headfile.h` 不带它）。
- **prereq**：空。**init**：`relay_init()` → **void** → 不写 `init_expect`。
- **接口名**：同 mspm0，`relay_init()` + `relay_set(uint8_t)`，无 on/off/toggle，无通道宏；
  `RELAY_ON_LEVEL 0u`（`relay_stm32.h:40`）。
- **probe**：同 mspm0 的动作式，无 expect。
- **read**（stm32 有真实回读，2 条）：

  | expression | unit |
  |---|---|
  | `gpio_get(RELAY_GPIO, RELAY_PIN)` | `PB4 引脚实际电平：1 = 引脚高 = 断开（正常收尾）；0 = 还在吸合（驱动/接线有问题）` |
  | `RELAY_ON_LEVEL` | `0 = 低电平吸合（实物高电平吸合改成 1）` |

- **console**：`e`（与 mspm0 同格）。
- **note 要点**：
  1. 默认 OUT = **PB4**（`pin_config.h:122-129`）。
  2. ⚠ **PB4 在 F103 上是 NJTRST / JTAG 复用脚**：作 GPIO 需 `SWJ_CFG` 释放 JTAG（保留 SWD）——
     库内把这条约束记在 `pin_config.h:436` 等，但**库内代码没有动 SWJ_CFG**。ST-Link 走 SWD
     下载不受影响；万一继电器完全不动、读数也不跟着变，先把 OUT 换到普通 GPIO 脚再试。
  3. **上电瞬间可能吸合一下（学生最容易被吓到的现象）**：`relay_init()` 先
     `gpio_init(..., OUT_PP)`（**只写 CRL/CRH、不写 ODR**）**再** `relay_set(0)`，而该引脚复位后
     ODR 位 = 0 → 这几条指令之间 **PB4 会输出低电平 = 吸合档**，随后才拉高。也就是"上电/复位的
     瞬间可能听到一声咔哒"。mspm0 侧没有这个问题。**建议上板确认后写进 note**。
  4. 撞脚：**PB4** 与 motor 编码器方向输入、hc05 KEY、lcd/oled SPI SCL、nrf24l01 MISO、rc522 MOSI
     等重叠（`tests/test_default_layout.py:172-178`）。
  5. 负载/感性说明同 mspm0；manifest 末句"**未上板**"。

---

## 4. 侦察中发现的库内驱动缺陷（按严重度）

**D1（最重要）servo/mspm0：周期 640000 超过 16 位定时器量程 —— 50Hz 出不来、>≈96° 输出恒高
（推断，需上板/SDK 复核）**

- 事实链：`SERVO_PWM` 时钟 = 32MHz（生成产物 `SERVO_PWM_INST_CLK_FREQ = 32000000`）；
  `servo_period() = 32000000/50 = 640000`（`servo_mspm0.c:9-12`）；`servo_init` 直接
  `DL_Timer_setLoadValue(SERVO_PWM_INST, 640000)`，而该 API 只做
  `gptimer->COUNTERREGS.LOAD = value;`（SDK `dl_timer.h:2560-2563`，无钳位），
  而 `DL_TIMER_PWM_MODE_EDGE_ALIGN` 的语义是 `LOAD = period-1`。
- 同仓旁证"量程是 16 位"：SysConfig 的 `timerCount` 写成上限 65535（`mspm0.syscfg:109`）；
  **同款写法的 step_motor 显式钳位**：`period = period < 65536 ? period : 65535;`
  （`library/modules/step_motor/code/step_motor.c:49`）——servo 没有这一步。
- 若 LOAD 16 位截断：`640000 & 0xFFFF = 50176` → 周期 ≈ **1.568ms（≈638Hz）**而不是 20ms；
  比较值 90°=48000（勉强 <50176）、**≈96° 以上超过周期 → 输出恒高**、180°=80000。
- 影响配方：mspm0 侧若写 `servo_set_angle(0,180)`，可能**完全不动**（不是舵机坏）。
- 库内测试**测不到**：`tests/test_module_servo.py:139-146` 自己就用 `period = 640000` 算占空比。

**D2（重要）joystick/mspm0：超时判据用"自旋次数"而不是时间 → X/Y 读数很可能恒 0（推断，需上板）**

- `_joystick_adc_read()`：`timeout = 50`，`while (BUSY_ACTIVE) { if (--timeout <= 0) return sum/(i?i:1); }`
  （`joystick.c:18,23-33`）→ 第一次采样（i=0）超时就 `return 0`。
- ADC12_0 是 **8 槽 sequence**、采样时间 `setSampleTime0(...,500)`、ADC 时钟 = ULPCLK/8
  → 500 ADC 周期 = 125µs/槽，**一次 startConversion 跑完整序列 ≈1ms**；
  50 次寄存器轮询 ≈ 几微秒~几十微秒 → **必然提前返回**。
- 后果：`joystick_read_x/y()` 在 mspm0 上会读到 **0**，而 **0% 恰好又是"杆推到端点"的合法读数**
  → 学生无法区分"坏了"和"推到端点"。同实例的 adc 模块用**无超时忙等**，读数是好的。
- 附带：adc 模块头注释说 MEM2/MEM3「adc_get 不开放」，但实现只挡 `> ADC_Channel_7`
  → 注释与实现不一致（低危，文档性）。

**D3（中等，现象类）relay/stm32：上电/复位瞬间可能吸合一下** —— 见 §3.2 note 要点 3
（`ml_gpio.c:13-59` 的 `gpio_init` 不写 ODR + 复位 ODR=0 + 低电平吸合 + `relay_stm32.c:34-36` 的顺序）。

**D4（文档漂移，会误导配方 note）joystick 的 ADC 槽数与实际不符**：`manifest.json:13` 与
`joystick.h:13-15`、`joystick.c:10-12` 都写"sequence **四通道** / endAdd=3"，而实际
`mspm0.syscfg:1294-1313` 是 **8 槽 / startAdd=0 / endAdd=7**（`CONTEXT.md:12` 又写"六通道"）
—— 三处口径各不相同。写 note 请按 syscfg 事实。

**D5（能力缺口）servo 的 `servo_id` / `channel` 形参被丢弃**：两侧实现都
`(void)servo_id; (void)channel;` → **多舵机/换通道调用是假接口**。

**D6（文档漂移）servo manifest 描述与头文件签名不一致**：manifest 写单参，头文件是**双参**。
配方必须按双参写。

**D7（易踩）relay 没有 `relay_on/off/toggle`、没有通道宏**：只有 `relay_init` / `relay_set(0|1)`
——凭常识写 `relay_on()` 会构建期红。

---

## 5. 写配方时的共同坑

1. **init_expect 千万别写**：三件 `init` 全是 void；写了会渲染 `r = joystick_init();` → 编译错。
2. **init/probe 多条调用 + expect 时，只有最后一条的返回值进比较** → 想让 servo/relay 做动作
   就必须放**不带 expect 的 probe**。
3. **平台头名互不相认**：`joystick.h`(mspm0) vs `joystick_stm32.h`(stm32)、`relay.h` vs
   `relay_stm32.h`；只有 servo 两平台共用 `servo.h`。写错 = include 段校验红。
4. **mspm0 侧任何 SysConfig/driverlib 名字都不能进配方**（母版无 .h）；stm32 侧 `pin_config.h` /
   `ml_*.h` 的名字全部可用（但 include 段要自己带上 `pin_config.h`）。
5. **read 里引用 `pin_config.h` 的宏，include 段必须写 `pin_config.h`**。
6. **跨模块头是"配方校验能过、生成期可能不许"**：想借 `adc_get` 绕过 D2 是不可靠的。
7. **read 表达式必须短**（标签 = 表达式前 60 字符）且**全整数**。
8. **"未判定"话术要翻译**：joystick/servo/relay 既没灯也没屏，note 要像 sr04 那样说清
   "这一件是看读数 / 听咔哒 / 看舵机臂"。
9. **正常范围一律写"应/理论 + 复测动作"**：三件都无上板记录。
10. **console 字符**：避开 `r/y/g/o/b/?` 与已占 `a d j k l m p s u x`；建议
    `t`(joystick) / `v`(servo) / `e`(relay)，`t/i/c/h` 是高争用区。
