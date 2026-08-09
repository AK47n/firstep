/**
 * @file    main.c
 * @brief   2026 电赛 C 题 —— 数字钥匙端程序
 *          主控: STM32F103C8T6
 *          功能: 上电即启动, 持续通过 DL-20 ZigBee 模块
 *                把 4 位拨码开关设定的钥匙 ID 发给门锁端
 *
 * 硬件连接:
 *   PA2  (USART2_TX) -> DL-20 的 RXD
 *   PA3  (USART2_RX) <- DL-20 的 TXD
 *   (若想换串口: 改下面 usart 初始化一处即可;
 *    可选 USART1 PA9/PA10, USART3 PB10/PB11)
 *   PB12~PB15 <- 4 位拨码开关 (bit0~bit3)
 *                拨码另一端接 GND, 用内部上拉:
 *                开关闭合(ON)= 读到 0 = 该位为 1
 *   PC13 -> 板载 LED (心跳指示, 低电平点亮)
 *
 * 数据帧格式 (4 字节, 门锁端按此解析):
 *   [0] 0xAA        帧头1
 *   [1] 0x55        帧头2
 *   [2] ID          4 位拨码值 (0x00~0x0F)
 *   [3] SUM         校验 = (0xAA + 0x55 + ID) & 0xFF
 *   每 100ms 发送一帧 (10Hz), 门锁端超时收不到即判"钥匙离场"
 */

#include "stm32f10x.h"

/* ---- 用户配置 -------------------------------------------------- */
#define ZIGBEE_BAUD     115200UL  /* 与 DL-20 模块配置的波特率保持一致 */
#define TX_PERIOD_MS    100u      /* 发送周期: 10Hz */

/* ---- 毫秒时基 (SysTick) ---------------------------------------- */
static volatile uint32_t g_ms = 0;

void SysTick_Handler(void)
{
    g_ms++;
}

static void delay_ms(uint32_t ms)
{
    uint32_t t0 = g_ms;
    while ((g_ms - t0) < ms) { }
}

/* ---- GPIO 初始化 ------------------------------------------------ */
static void gpio_init(void)
{
    /* 打开 GPIOA / GPIOB / GPIOC 时钟 */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN
                  | RCC_APB2ENR_IOPBEN
                  | RCC_APB2ENR_IOPCEN;

    /* PA2 (USART2_TX): 复用推挽输出, 50MHz  -> CRL[11:8] = 1011 = 0xB */
    GPIOA->CRL &= ~(0xFu << 8);
    GPIOA->CRL |=  (0xBu << 8);

    /* PA3 (USART2_RX): 浮空输入             -> CRL[15:12] = 0100 = 0x4 */
    GPIOA->CRL &= ~(0xFu << 12);
    GPIOA->CRL |=  (0x4u << 12);

    /* PB12~PB15 (拨码): 上拉输入 -> CNF=10, MODE=00, ODR=1 */
    GPIOB->CRH &= ~(0xFFFFu << 16);          /* 清掉 pin12~15 的配置位 */
    GPIOB->CRH |=  (0x8888u << 16);          /* CNF=10 MODE=00 */
    GPIOB->ODR |=  (0xFu << 12);             /* ODR=1 -> 内部上拉 */

    /* PC13 (LED): 推挽输出, 2MHz -> CRH[23:20] = 0010 = 0x2 */
    GPIOC->CRH &= ~(0xFu << 20);
    GPIOC->CRH |=  (0x2u << 20);
    GPIOC->ODR |=  (1u << 13);               /* 默认熄灭 */
}

/* ---- USART2 初始化 (APB1 = 36MHz) ------------------------------ */
static void usart_init(void)
{
    RCC->APB1ENR |= RCC_APB1ENR_USART2EN;

    /* 波特率: BRR = PCLK1 / baud */
    USART2->BRR = (36000000UL + ZIGBEE_BAUD / 2) / ZIGBEE_BAUD;

    USART2->CR1 = USART_CR1_TE      /* 使能发送 */
                | USART_CR1_RE      /* 使能接收(备用) */
                | USART_CR1_UE;     /* 使能串口, 8N1 */
}

static void usart_send_byte(uint8_t b)
{
    while (!(USART2->SR & USART_SR_TXE)) { }
    USART2->DR = b;
}

/* ---- 读取 4 位拨码开关 ------------------------------------------
 * 拨码 ON(闭合到 GND) -> 引脚读到 0 -> 该位记为 1
 * 返回 0x00~0x0F
 */
static uint8_t read_key_id(void)
{
    uint16_t pin = GPIOB->IDR;
    uint8_t id = 0;

    if (!(pin & (1u << 12))) id |= 0x1;   /* bit0 */
    if (!(pin & (1u << 13))) id |= 0x2;   /* bit1 */
    if (!(pin & (1u << 14))) id |= 0x4;   /* bit2 */
    if (!(pin & (1u << 15))) id |= 0x8;   /* bit3 */

    return id & 0x0F;
}

/* ---- 发送一帧 ID ----------------------------------------------- */
static void send_id_frame(uint8_t id)
{
    uint8_t sum = (uint8_t)(0xAAu + 0x55u + id);

    usart_send_byte(0xAA);
    usart_send_byte(0x55);
    usart_send_byte(id);
    usart_send_byte(sum);
}

/* ---- 主函数 ----------------------------------------------------- */
int main(void)
{
    /* SystemInit() 已由启动文件调用: 8MHz HSE 经 PLL 到 72MHz */

    gpio_init();
    usart_init();

    /* SysTick 1ms 中断: 72MHz / 1000 = 72000 */
    SysTick->LOAD = 72000u - 1u;
    SysTick->VAL  = 0;
    SysTick->CTRL = SysTick_CTRL_CLKSOURCE_Msk
                  | SysTick_CTRL_TICKINT_Msk
                  | SysTick_CTRL_ENABLE_Msk;

    while (1)
    {
        uint8_t id = read_key_id();   /* 每帧发送前都重读,
                                         拨码改动立即生效 */
        send_id_frame(id);

        GPIOC->ODR ^= (1u << 13);     /* LED 翻转, 表示正在工作 */

        delay_ms(TX_PERIOD_MS);
    }
}
