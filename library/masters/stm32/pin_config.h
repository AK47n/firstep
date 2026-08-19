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
