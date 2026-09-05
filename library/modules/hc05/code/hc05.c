#include "hc05.h"
#include "ti_msp_dl_config.h"

/* HC-05 蓝牙串口透传（mspm0 纯驱动）：
 * RX 中断把字节写入环形缓冲（zigbee_uart 先例），主循环 hc05_receive 读走；
 * 发送忙等 UART 不忙后逐字节写；连接状态读 STATE 引脚；AT 切换驱动 KEY 脚
 * （重新上电生效）。立创原版 BLERX_BUFF[200] + 单 FLAG 缓冲改环形缓冲
 * （原版每字节覆盖 + 长度上限截断，读侧无环形语义）。 */

static volatile uint8_t _rx_buf[HC05_RX_BUF_SIZE];
static volatile uint16_t _rx_head = 0; /* 下一次写入位置 */
static volatile uint16_t _rx_tail = 0; /* 下一次读取位置 */

void hc05_init(void)
{
    NVIC_ClearPendingIRQ(HC05_UART_INST_INT_IRQN);
    NVIC_EnableIRQ(HC05_UART_INST_INT_IRQN);

    _rx_head = 0;
    _rx_tail = 0;

    /* KEY 默认拉低 = 透传模式（进入 AT 需重新上电并保持 KEY 高） */
    DL_GPIO_clearPins(HC05_KEY_PORT, HC05_KEY_PIN);
}

void hc05_send_char(uint8_t ch)
{
    while (DL_UART_isBusy(HC05_UART_INST) == true) {
        /* 忙等 TX 空闲 */
    }
    DL_UART_Main_transmitData(HC05_UART_INST, ch);
}

void hc05_send_string(const char *str)
{
    while (str && *str) {
        hc05_send_char((uint8_t)*str++);
    }
}

void hc05_send_buffer(const uint8_t *buf, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++) {
        hc05_send_char(buf[i]);
    }
}

uint16_t hc05_available(void)
{
    uint16_t head = _rx_head;
    uint16_t tail = _rx_tail;
    return (uint16_t)((head + HC05_RX_BUF_SIZE - tail) % HC05_RX_BUF_SIZE);
}

uint16_t hc05_receive(uint8_t *buf, uint16_t max_len)
{
    uint16_t count = 0;
    while (count < max_len && _rx_tail != _rx_head) {
        buf[count++] = _rx_buf[_rx_tail];
        _rx_tail = (uint16_t)((_rx_tail + 1) % HC05_RX_BUF_SIZE);
    }
    return count;
}

void hc05_clear_rx(void)
{
    _rx_head = 0;
    _rx_tail = 0;
}

uint8_t hc05_is_connected(void)
{
    uint32_t bits = DL_GPIO_readPins(HC05_STATE_PORT, HC05_STATE_PIN);
    uint8_t level = (bits & HC05_STATE_PIN) ? 1 : 0;
    return (level == HC05_CONNECTED_LEVEL) ? 1 : 0;
}

void hc05_at_mode_enter(void)
{
    /* HC05 硬件：KEY 高电平 + 重新上电 = AT 命令模式（默认 38400）；
     * 程序内切换后必须断电重启才生效，此处仅驱动引脚电平并注释说明。 */
    DL_GPIO_setPins(HC05_KEY_PORT, HC05_KEY_PIN);
}

void hc05_at_mode_exit(void)
{
    DL_GPIO_clearPins(HC05_KEY_PORT, HC05_KEY_PIN);
}

/* HC05_UART_INST_IRQHandler = UART2_IRQHandler（母版 SysConfig 宏）。
 * 仅处理 RX 中断；环形缓冲满时丢新字节（读侧不消费时的背压策略）。 */
void HC05_UART_INST_IRQHandler(void)
{
    switch (DL_UART_getPendingInterrupt(HC05_UART_INST))
    {
    case DL_UART_IIDX_RX:
    {
        uint8_t byte = (uint8_t)DL_UART_receiveData(HC05_UART_INST);
        uint16_t next = (uint16_t)((_rx_head + 1) % HC05_RX_BUF_SIZE);
        if (next != _rx_tail) {
            _rx_buf[_rx_head] = byte;
            _rx_head = next;
        }
        break;
    }
    default:
        break;
    }
}
