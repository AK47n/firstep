/**
 * ============================================================
 * 数字钥匙端（信标端）固件 — MSPM0G3507 地猛星
 * ============================================================
 *
 * 功能：每 100ms 读取 4 位 DIP 拨码开关，通过 DL-20 ZigBee
 *       模块发送 4 字节数据帧 [AA 55 ID SUM]。
 *
 * 接线：
 *   DL-20 RXD  → PB6 (UART1 TX)
 *   DL-20 TXD  → PB7 (UART1 RX)（本程序只发不收，保留初始化）
 *   DIP bit0   → PA12（上拉，ON=0=该位为1）
 *   DIP bit1   → PA13（上拉，ON=0=该位为1）
 *   DIP bit2   → PA14（上拉，ON=0=该位为1）
 *   DIP bit3   → PA15（上拉，ON=0=该位为1）
 *
 * 数据帧格式（4 字节，不可修改）：
 *   [0] 0xAA  同步头1
 *   [1] 0x55  同步头2
 *   [2] ID    钥匙 ID（0x00～0x0F，取低 4 位）
 *   [3] SUM   校验和 = (0xAA + 0x55 + ID) & 0xFF
 */

#include "ti_msp_dl_config.h"

/* ============================================================
 * 全局变量
 * ============================================================ */

/** SysTick 毫秒计数器（由 SysTick_Handler 每秒 1000 次递增） */
static volatile uint32_t g_tick_ms = 0;

/* ============================================================
 * SysTick 中断服务
 * ============================================================ */

void SysTick_Handler(void)
{
    g_tick_ms++;
}

/* ============================================================
 * UART 发送函数
 * ============================================================ */

/**
 * @brief 通过 DL20 UART 发送一个字节（阻塞，等待 TX FIFO 就绪）
 */
static void uart_send_byte(uint8_t data)
{
    DL_UART_Main_transmitDataBlocking(DL20_INST, data);
}

/**
 * @brief 发送一帧数据：AA 55 ID SUM
 * @param id  钥匙 ID（0x00～0x0F）
 */
static void send_key_frame(uint8_t id)
{
    uint8_t sum = (0xAA + 0x55 + id) & 0xFF;

    uart_send_byte(0xAA);
    uart_send_byte(0x55);
    uart_send_byte(id);
    uart_send_byte(sum);
}

/* ============================================================
 * DIP 拨码读取
 * ============================================================ */

/**
 * @brief 读取 4 位 DIP 拨码开关，返回 0x00～0x0F
 *
 * 拨码 ON（闭合到 GND） → GPIO 读到 0 → 该位 = 1
 * 拨码 OFF（断开）       → GPIO 读到 1 → 该位 = 0
 *
 * 位序（与门锁端约定一致）：
 *   第1位(最左) PA12 = bit0 (LSB) = 0x01
 *   第2位       PA13 = bit1       = 0x02
 *   第3位       PA14 = bit2       = 0x04
 *   第4位(最右) PA15 = bit3 (MSB) = 0x08
 */
static uint8_t read_dip(void)
{
    uint8_t id = 0;

    if (DL_GPIO_readPins(KEY_FOB_PORT, KEY_FOB_DIP0_PIN) == 0) {
        id |= 0x01;   /* DIP bit0 ON → ID bit0 = 1 */
    }
    if (DL_GPIO_readPins(KEY_FOB_PORT, KEY_FOB_DIP1_PIN) == 0) {
        id |= 0x02;   /* DIP bit1 ON → ID bit1 = 1 */
    }
    if (DL_GPIO_readPins(KEY_FOB_PORT, KEY_FOB_DIP2_PIN) == 0) {
        id |= 0x04;   /* DIP bit2 ON → ID bit2 = 1 */
    }
    if (DL_GPIO_readPins(KEY_FOB_PORT, KEY_FOB_DIP3_PIN) == 0) {
        id |= 0x08;   /* DIP bit3 ON → ID bit3 = 1 */
    }

    return id;
}

/* ============================================================
 * 主函数
 * ============================================================ */

int main(void)
{
    /* ---- 1. 初始化外设（syscfg 生成） ---- */
    SYSCFG_DL_init();

    /* ---- 2. 配置 SysTick：1ms 中断（80MHz / 1000 = 80000） ---- */
    SysTick_Config(CPUCLK_FREQ / 1000);

    /* ---- 3. 主循环：每 100ms 读 DIP → 发帧 ---- */
    uint32_t next_tick = g_tick_ms + 100;

    while (1) {
        /* 等待下一个 100ms 边界（绝对时间，无累积漂移） */
        while ((int32_t)(g_tick_ms - next_tick) < 0) {
            /* 空转，SysTick ISR 会递增 g_tick_ms */
        }
        next_tick += 100;

        /* 读取 DIP 拨码 */
        uint8_t id = read_dip();

        /* 发送数据帧 */
        send_key_frame(id);
    }
}
