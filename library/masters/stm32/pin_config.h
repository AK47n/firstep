#ifndef __PIN_CONFIG_H
#define __PIN_CONFIG_H

/* ============================================================
 * 接线单源：全工程引脚集中配置（ADR 0010，值 = 迁移前硬编码原值）
 *
 * 改引脚只动本文件（对偶 mspm0 侧 SysConfig 生成的实例宏）：模块代码
 * （motor_stm32.c / gray_track.c / digit_uart.c / debug_uart.c /
 * coord_detect_stm32.c / uwb_uart.c / zigbee_uart.c 等）只引用这些宏、
 * 不写死引脚字面量。config 模块的 config.h 保留非引脚参数并 include
 * 本文件——原 LED/蜂鸣器/DIP/UWB/Zigbee 引脚宏已并入此处。
 *
 * ⚠️ EXTI 中断名绑定引脚线号：PA2 → EXTI2_IRQHandler、PA4 →
 * EXTI4_IRQHandler 固定，编码器线一换，对应 handler 名也要换（中断
 * 代码整体留在模块内可替换位置）。
 * ============================================================ */

/* ---- ADC（模拟采样，adc 模块；通道枚举 = ml_adc 的 ADCINx_enum）---- */
#define ADC_0_CH   ADC_Channel_0   /* PA0 */
#define ADC_1_CH   ADC_Channel_1   /* PA1 */
/* ---- PWM（电机调速，频率 1000Hz = 21F 原值）---- */
#define MOTOR_A_PWM_TIM     TIM_2
#define MOTOR_A_PWM_CH      TIM2_CH1   /* PA0 */
#define MOTOR_B_PWM_TIM     TIM_2
#define MOTOR_B_PWM_CH      TIM2_CH2   /* PA1 */
#define MOTOR_PWM_FREQ      1000

/* ---- 舵机（servo 模块：50Hz/20ms，0.5-2.5ms 脉宽 = 0-180°；TIM4_CH1 = PB6）---- */
#define SERVO_PWM_TIM   TIM_4
#define SERVO_PWM_CH    TIM4_CH1   /* PB6 */
/* ---- 方向（TB6612 AIN1/AIN2、BIN1/BIN2，21F 原值）---- */
#define MOTOR_A_DIR_PORT    GPIO_A
#define MOTOR_A_DIR_PIN     Pin_6
#define MOTOR_A_DIR2_PORT   GPIO_A
#define MOTOR_A_DIR2_PIN    Pin_7
#define MOTOR_B_DIR_PORT    GPIO_B
#define MOTOR_B_DIR_PIN     Pin_0
#define MOTOR_B_DIR2_PORT   GPIO_B
#define MOTOR_B_DIR2_PIN    Pin_1

/* ---- 编码器（EXTI 脉冲计数 + 方向输入；A 编码器已离 PA2/PA3 让位 DEBUG_UART）---- */
#define MOTOR_A_ENC_EXTI      EXTI_PB5   /* PB5，下降沿触发 */
#define MOTOR_A_ENC_LINE      5          /* EXTI 线号（handler 按此条件编译） */
#define MOTOR_A_ENC_DIR_PORT  GPIO_B
#define MOTOR_A_ENC_DIR_PIN   Pin_4      /* 方向输入（上拉） */
#define MOTOR_B_ENC_EXTI      EXTI_PA4   /* PA4，下降沿触发 */
#define MOTOR_B_ENC_LINE      4          /* EXTI 线号（handler 按此条件编译） */
#define MOTOR_B_ENC_DIR_PORT  GPIO_A
#define MOTOR_B_ENC_DIR_PIN   Pin_5      /* 方向输入（上拉） */

/* ---- 灰度传感器（pid 模块 gray_track.c：D1-D8 输入上拉；D6-D8 已离 PC13-15 让位 LED）---- */
#define GRAY_D1_PORT  GPIO_B
#define GRAY_D1_PIN   Pin_12
#define GRAY_D2_PORT  GPIO_B
#define GRAY_D2_PIN   Pin_13
#define GRAY_D3_PORT  GPIO_B
#define GRAY_D3_PIN   Pin_14
#define GRAY_D4_PORT  GPIO_B
#define GRAY_D4_PIN   Pin_15
#define GRAY_D5_PORT  GPIO_A
#define GRAY_D5_PIN   Pin_8
#define GRAY_D6_PORT  GPIO_B
#define GRAY_D6_PIN   Pin_3
#define GRAY_D7_PORT  GPIO_B
#define GRAY_D7_PIN   Pin_6
#define GRAY_D8_PORT  GPIO_B
#define GRAY_D8_PIN   Pin_7

/* ---- K230 视觉串口（digit_uart / coord_detect 模块，115200）----
 * UART 实例宏（ml_uart 的 UARTn_enum）+ 寄存器实例宏（UART_1 ↔ USART1，
 * UART_2 ↔ USART2）+ 引脚宏（TX_GPIO/TX_Pin/RX_GPIO/RX_Pin，值 = ml_uart
 * switch 表原值——换实例换引脚随绑定渲染，模块 init 传宏走 uart_pin_init_ex）。
 */
#define DIGIT_UART             UART_1
#define DIGIT_UART_INST        USART1
#define DIGIT_UART_TX_GPIO GPIO_A
#define DIGIT_UART_TX_Pin Pin_9
#define DIGIT_UART_RX_GPIO GPIO_A
#define DIGIT_UART_RX_Pin Pin_10
#define COORD_DETECT_UART       UART_1
#define COORD_DETECT_UART_INST  USART1
#define COORD_DETECT_UART_TX_GPIO GPIO_A
#define COORD_DETECT_UART_TX_Pin Pin_9
#define COORD_DETECT_UART_RX_GPIO GPIO_A
#define COORD_DETECT_UART_RX_Pin Pin_10

/* ---- 调试串口（debug_uart 模块，115200）---- */
#define DEBUG_UART             UART_2
#define DEBUG_UART_INST        USART2
#define DEBUG_UART_TX_GPIO GPIO_A
#define DEBUG_UART_TX_Pin Pin_2
#define DEBUG_UART_RX_GPIO GPIO_A
#define DEBUG_UART_RX_Pin Pin_3

/* ---- 三色 LED（config.h 并入：共阴，高电平点亮，PC13-15）---- */
#define LED_PORT          GPIO_C
#define LED_RED_PIN       Pin_13   /* 红灯 */
#define LED_YELLOW_PIN    Pin_14   /* 黄灯 */
#define LED_GREEN_PIN     Pin_15   /* 绿灯 */

/* ---- 蜂鸣器（config.h 并入：有源蜂鸣器，低电平触发；已离 PB0 让位 MOTOR_B_DIR）---- */
#define BUZZER_GPIO       GPIO_A
#define BUZZER_PIN        Pin_15

/* ---- DIP-4 拨码开关（config.h 并入：4 位二进制 ID，上拉输入，拨到 ON=低电平）---- */
#define DIP_GPIO          GPIO_B
#define DIP_PIN0          Pin_12
#define DIP_PIN1          Pin_13
#define DIP_PIN2          Pin_14
#define DIP_PIN3          Pin_15

/* ---- 按键（key 模块 stm32 默认 PB3 = JTDO，SWD 调试用不到；上拉输入，按下=低电平）---- */
#define KEY_GPIO          GPIO_B
#define KEY_PIN           Pin_3

/* ---- 红外对射传感器（ir_beam 模块：三线制 VCC/GND/OUT，OUT 默认 PA8；
 * 内部上拉输入，遮挡=高电平（同 21F 药位检测）；与 pid 灰度 GRAY_D5 默认
 * 重叠 PA8——同选时经引脚绑定消解）---- */
#define IR_BEAM_GPIO          GPIO_A
#define IR_BEAM_PIN           Pin_8

/* ---- 继电器（relay 模块：GPIO 输出 1 脚，OUT 默认 PB4——与 motor 编码器
 * 方向输入 MOTOR_A_ENC_DIR 默认重叠：继电器与「带编码器闭环的电机控制」
 * 不同框、同选概率最低（刻意不叠声光/执行件 LED/BUZZER/电机 PWM/方向——
 * 继电器+蜂鸣报警/电灯控制为常见组合），同选时经引脚绑定消解；PB4 非
 * PWM/ADC 主用脚，推挽输出无扰。页面（地阔星 F4 口径）默认 PA2 不采用
 * ——DEBUG_UART TX 常备件）---- */
#define RELAY_GPIO            GPIO_B
#define RELAY_PIN             Pin_4

/* ---- 人体红外传感器（human_ir 模块：HC-SR501 三线制，OUT 默认 PB7——与
 * pid 灰度 GRAY_D8 默认重叠：人体红外与「巡线灰度」不同框、同选概率最低
 * （刻意避让声光/按键/门禁组合 BUZZER/KEY/SERVO），同选时经引脚绑定消解；
 * 页面默认 PA1 不采用——被 adc ADC_CH1/motor PWM/编码器线占用）---- */
#define HUMAN_IR_GPIO         GPIO_B
#define HUMAN_IR_PIN          Pin_7

/* ---- 微波多普勒雷达（microwave_radar 模块：HB100 三线制，OUT 默认 PA4——
 * 与 motor 编码器 B 相（MOTOR_B_ENC，EXTI 线 4/PA4）默认重叠：微波雷达与
 * 「带编码器闭环的电机控制」不同框、同选概率最低（刻意避让声光/门禁/传感
 * 站组合件），同选时经引脚绑定消解；本件轮询不注册 EXTI，与编码器线共享
 * 正交（异口同线此时不冲突）；页面默认 PA1 不采用——叠 adc ADC_CH1 +
 * MOTOR_B_PWM 常备件）---- */
#define MICROWAVE_GPIO        GPIO_A
#define MICROWAVE_PIN         Pin_4

/* ---- 火焰传感器（flame 模块：AO 模拟输出 → ADC1 通道，默认
 * ADC_Channel_5 = PA5——**页面原脚**（用户照页面接线即插即用）；独立通道
 * ——与 adc 模块 ADC_CH0/1 不共读（ml_adc 的 adc_get 每次先写 SQR3 选通道，
 * 顺序调用互不干扰）；PA5 现状叠 motor MOTOR_B_ENC_DIR（编码器方向输入，
 * gpio_in）——火焰与「带编码器闭环的电机控制」不同框、同选概率最低，同选
 * 经引脚绑定消解（换其它 ADC 脚 PA0-7/PB0-1；页面 DO=PA6 未用不声明——
 * LM393 阈值由模块可调电阻控制）---- */
#define FLAME_AO_CH           ADC_Channel_5

/* ---- 批次 5（wiki-stm32-batch5）：ADC 薄封装群一 8 件（mq2/mq135/mq5/
 * photoresistance/rain/s12sd/soil/gp2y1014au——AO 模拟量 + 百分比/档位换算
 * 同构件，页面 ADC 序列代码全部收敛 ml_adc）----
 * 默认 AO 全 = ADC_Channel_5 = PA5（页面原脚即共读点——用户照页面接线
 * 即插即用）；**ADC 共享组**：8 件与 flame 共读 PA5（ml_adc 的 adc_get
 * 每次先写 SQR3 选通道再触发转换，顺序调用互不干扰——flame 先例注释确认；
 * 同一物理脚只能接一件器件，多件同测需外部分路器/分时切换——mspm0 MEM0
 * 共读同口径；stm32 可达 ADC 脚 PA0-7/PB0-1 全被既有角色占用，页面原脚
 * 即共读点），同选经引脚绑定消解（换其它 ADC 脚）；
 * gp2y1014au LED 驱动（器件必需——低有效脉冲）：默认 PB5（页面原脚
 * PA2 = DEBUG_UART TX 常备件不照抄；PB5 叠 hx711 SCK + MOTOR_A_ENC——
 * 粉尘与称重/光电编码器闭环不同框、同选概率最低）。 */
#define MQ2_AO_CH             ADC_Channel_5
#define MQ135_AO_CH           ADC_Channel_5
#define MQ5_AO_CH             ADC_Channel_5
#define PHOTORESISTANCE_AO_CH ADC_Channel_5
#define RAIN_AO_CH            ADC_Channel_5
#define S12SD_AO_CH           ADC_Channel_5
#define SOIL_AO_CH            ADC_Channel_5
#define GP2Y1014_AO_CH        ADC_Channel_5
#define GP2Y1014_LED_GPIO     GPIO_B
#define GP2Y1014_LED_PIN      Pin_5

/* ---- TTP224 四路电容触摸（ttp224 模块：4 × GPIO 输入下拉，OUT1-4 默认
 * PB12/13/14/15——与 config DIP0-3（拨码 ID）+ pid 灰度 GRAY_D1-4 默认重叠：
 * 触摸按键与「拨码系统配置/巡线灰度」不同框、同选概率最低（触摸+无线链路
 * 互替/手动输入同框低），同选时经引脚绑定消解——**同口绑定约束：四脚须同
 * GPIO 口（共享 TTP224_GPIO 宏），换口需整组迁移**；页面默认 PA1-4 不采用
 * ——全被既有角色占用）---- */
#define TTP224_GPIO           GPIO_B
#define TTP224_OUT1_PIN       Pin_12
#define TTP224_OUT2_PIN       Pin_13
#define TTP224_OUT3_PIN       Pin_14
#define TTP224_OUT4_PIN       Pin_15

/* ---- WS2812 幻彩灯带（ws2812 模块：单 GPIO 位时序输出 1 脚，DIN 默认
 * PA8——与 ir_beam 对射 + pid 灰度 GRAY_D5 默认重叠：幻彩灯带与「红外对射/
 * 巡线」不同框、同选概率最低（刻意不叠灯族 LED PC13-15 板载灯——彩灯常
 * 代替板载灯做指示，同框概率高；与声光件亦不叠），同选时经引脚绑定消解；
 * 页面默认 PB12 不采用——本批 ttp224 四脚 + DIP/GRAY 三重叠已占；PA8 无
 * 特殊引脚阻塞，F103 72MHz 忙等 1.25us/位——不占 TIM/PWM）---- */
#define WS2812_GPIO           GPIO_A
#define WS2812_PIN            Pin_8

/* ---- 软 I2C 总线件（aht10/bh1750/sht20/sht30/at24c02/ags10 六件，macros
 * 逐脚端口宏——SCL/SDA 可分别绑定任意脚，无同口约束）：默认共挂一总线
 * PA6（SCL）/PA7（SDA）——六件器件地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异、
 * 多挂协议允许 = 合法共享（test_default_layout 白名单登记）；PA6/PA7 与
 * motor MOTOR_A_DIR/DIR2（TB6612 A 相方向）默认重叠：环境传感/存储记录与
 * 「带电机方向的小车运动控制」不同框、同选概率最低（刻意不叠显示/声光/
 * 输入/串口/无线/USB(PA11/12)/SWD(PA13/14) 组——见 wiki-stm32-batch2
 * spec 默认脚推理；与既有 I2C_GPIO（PA11/12）、OLED_GPIO（PB8/9）零重叠
 * 独立并存，同选 = 三总线各自独立），同选时经引脚绑定消解；**页面默认脚
 * 全不照抄**（aht10 页面 PB8/PB9 = OLED 段、其余页面默认见各件 notes）---- */
#define AHT10_SCL_GPIO        GPIO_A
#define AHT10_SCL_PIN         Pin_6
#define AHT10_SDA_GPIO        GPIO_A
#define AHT10_SDA_PIN         Pin_7
#define BH1750_SCL_GPIO       GPIO_A
#define BH1750_SCL_PIN        Pin_6
#define BH1750_SDA_GPIO       GPIO_A
#define BH1750_SDA_PIN        Pin_7
#define SHT20_SCL_GPIO        GPIO_A
#define SHT20_SCL_PIN         Pin_6
#define SHT20_SDA_GPIO        GPIO_A
#define SHT20_SDA_PIN         Pin_7
#define SHT30_SCL_GPIO        GPIO_A
#define SHT30_SCL_PIN         Pin_6
#define SHT30_SDA_GPIO        GPIO_A
#define SHT30_SDA_PIN         Pin_7
#define AT24C02_SCL_GPIO      GPIO_A
#define AT24C02_SCL_PIN       Pin_6
#define AT24C02_SDA_GPIO      GPIO_A
#define AT24C02_SDA_PIN       Pin_7
#define AGS10_SCL_GPIO        GPIO_A
#define AGS10_SCL_PIN         Pin_6
#define AGS10_SDA_GPIO        GPIO_A
#define AGS10_SDA_PIN         Pin_7
/* ---- 批次 3（wiki-stm32-batch3）：软 I2C 器件库五件 + HX711 称重 ----
 * I2C 五件（ads1115/tcs34725/mlx90614/sgp30/pca9685）默认与批次 2 六件
 * 共挂同一软 I2C 总线 PA6/PA7（地址 0x48/0x29/0x5A/0x58/0x40 与既有
 * 0x38/0x23/0x40/0x44/0x50/0x1A 全异——**pca9685 0x40 × sht20 0x40 同址**：
 * 同选时 pca9685_set_address(1)（0x41，A5 接线）或绑定换独立总线；
 * 与 motor MOTOR_A_DIR/DIR2 默认重叠：传感/驱动与「带电机方向的小车
 * 运动控制」不同框、同选概率最低，同选经引脚绑定消解）；
 * HX711 独立 GPIO 双线 默认 SCK=PB5 / DT=PB0（PB5 叠 MOTOR_A_ENC——
 * 光电编码器闭环小车与静态称重/电子秤不同框；PB0 叠 MOTOR_B_DIR——
 * TB6612 B 相方向与称重不同框；刻意不叠本批 I2C 件与采集类（flame/
 * ir_beam/human_ir 等——称重+传感站常见组合）与声光件）。 */
#define ADS1115_SCL_GPIO      GPIO_A
#define ADS1115_SCL_PIN       Pin_6
#define ADS1115_SDA_GPIO      GPIO_A
#define ADS1115_SDA_PIN       Pin_7
#define TCS34725_SCL_GPIO     GPIO_A
#define TCS34725_SCL_PIN      Pin_6
#define TCS34725_SDA_GPIO     GPIO_A
#define TCS34725_SDA_PIN      Pin_7
#define MLX90614_SCL_GPIO     GPIO_A
#define MLX90614_SCL_PIN      Pin_6
#define MLX90614_SDA_GPIO     GPIO_A
#define MLX90614_SDA_PIN      Pin_7
#define SGP30_SCL_GPIO        GPIO_A
#define SGP30_SCL_PIN         Pin_6
#define SGP30_SDA_GPIO        GPIO_A
#define SGP30_SDA_PIN         Pin_7
#define PCA9685_SCL_GPIO      GPIO_A
#define PCA9685_SCL_PIN       Pin_6
#define PCA9685_SDA_GPIO      GPIO_A
#define PCA9685_SDA_PIN       Pin_7
#define HX711_SCK_GPIO        GPIO_B
#define HX711_SCK_PIN         Pin_5
#define HX711_DT_GPIO         GPIO_B
#define HX711_DT_PIN          Pin_0

/* ---- 批次 4（wiki-stm32-batch4）：气压组两件（软 I2C，共挂批次 2/3
 * 总线 PA6/PA7）----
 * bmp180/ms5611 默认 SCL=PA6/SDA=PA7——地址 0xEE（7bit 0x77）与既有 11 件
 * 0x38/0x23/0x40/0x44/0x50/0x1A/0x48/0x29/0x5A/0x58/0x40 全异 = 合法共挂；
 * **bmp180 × ms5611 同址 0xEE = 互替件不可同挂**（同一总线同址双选必冲突
 * ——选一只；同选时经引脚绑定换独立总线或换件）；与 motor MOTOR_A_DIR/
 * DIR2（TB6612 A 相方向）默认重叠：气压/海拔与「带电机方向的小车运动
 * 控制」不同框、同选概率最低，同选经引脚绑定消解；页面默认 PB8/PB9
 * （=OLED 段）不采用（批次 2 先例）。 */
#define BMP180_SCL_GPIO       GPIO_A
#define BMP180_SCL_PIN        Pin_6
#define BMP180_SDA_GPIO       GPIO_A
#define BMP180_SDA_PIN        Pin_7
#define MS5611_SCL_GPIO       GPIO_A
#define MS5611_SCL_PIN        Pin_6
#define MS5611_SDA_GPIO       GPIO_A
#define MS5611_SDA_PIN        Pin_7

/* ---- 批次 4：单总线件（dht11 温湿度 / ds18b20 测温——单 GPIO 双向，
 * 方向运行时重配 + delay_us 忙等，不占 TIMER/PWM）----
 * default DATA：dht11=PB3（叠 key.KEY_START + pid.GRAY_D6——环境件与独立
 * 按键/巡线灰度不同框、同选概率最低；刻意不叠声光/显示/传感站组合——温
 * 湿度+声光/显示为常见搭配；单总线件与软 I2C 总线件 PA6/PA7 不共脚；
 * 页面默认 PB0 不采用 = MOTOR_B_DIR）；ds18b20=PB1（叠 MOTOR_B_DIR2——
 * 测温与单电机方向不同框；刻意不叠声光/传感站/总线环境件——测温+声光/
 * 环境站为常见搭配；页面默认 PB0 不采用 = MOTOR_B_DIR）。 */
#define DHT11_GPIO            GPIO_B
#define DHT11_PIN             Pin_3
#define DS18B20_GPIO          GPIO_B
#define DS18B20_PIN           Pin_1

/* ---- UWB 基站串口（config.h 并入：UART_1 = PA9 TX / PA10 RX，115200）---- */
#define UWB_UART          UART_1
#define UWB_UART_INST     USART1
#define UWB_UART_TX_GPIO GPIO_A
#define UWB_UART_TX_Pin Pin_9
#define UWB_UART_RX_GPIO GPIO_A
#define UWB_UART_RX_Pin Pin_10

/* ---- Zigbee 无线串口（config.h 并入：UART_3 = PB10 TX / PB11 RX，115200）---- */
#define ZIGBEE_UART       UART_3
#define ZIGBEE_UART_INST  USART3
#define ZIGBEE_UART_TX_GPIO GPIO_B
#define ZIGBEE_UART_TX_Pin Pin_10
#define ZIGBEE_UART_RX_GPIO GPIO_B
#define ZIGBEE_UART_RX_Pin Pin_11

/* ---- UART 接收中断聚合（isr.c 的 USARTx_IRQHandler 调这些宏，
 * 工单 pin-full-unlock/02）——按各 UART 角色绑定实例重分组：默认
 * UART_1 = DIGIT+COORD+UWB 共享、UART_2 = DEBUG、UART_3 = ZIGBEE。 ---- */
#define USART1_IRQ_CALLS digit_uart_rx_handler(); coord_detect_rx_handler(); uwb_rx_handler();
#define USART2_IRQ_CALLS debug_uart_rx_handler();
#define USART3_IRQ_CALLS zigbee_rx_handler();

/* ---- 软 I2C（ml_i2c / ml_oled 引脚宏，自 ml_libs 头文件迁入）----
 * 参数化后 I2C 角色可绑任意 GPIO（ADR 0011 工单 02）：ml_i2c 默认 PA11 SCL /
 * PA12 SDA（已离 PB10/11 让位 Zigbee UART_3；PA11/PA12 为 USB DM/DP 共用脚，
 * 用 USB 时勿占用）、ml_oled 默认 PB8 SCL / PB9 SDA。
 */
#define I2C_GPIO          GPIO_A
#define I2C_SCL_GPIO_Pin  Pin_11
#define I2C_SDA_GPIO_Pin  Pin_12
#define OLED_GPIO         GPIO_B
#define OLED_SCL_Pin      Pin_8
#define OLED_SDA_Pin      Pin_9

#endif /* __PIN_CONFIG_H */
