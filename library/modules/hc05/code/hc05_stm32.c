/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《HC05蓝牙模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/hc05-bluetooth-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "hc05_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* HC-05 蓝牙串口透传（stm32 纯驱动）：RX 中断把字节写入环形缓冲
 * （hc05_rx_handler 经母版 isr.c 聚合调用——coord_detect/digit 先例），
 * 主循环 hc05_receive 读走；发送忙等 TX 完成后逐字节写；连接状态读 STATE
 * 引脚；AT 切换驱动 KEY 脚（重新上电生效）。立创原版 BLERX_BUFF[200] +
 * 单 FLAG 缓冲改环形缓冲（原版每字节覆盖 + 长度上限截断，读侧无环形语义）。 */

static volatile uint8_t _rx_buf[HC05_RX_BUF_SIZE];
static volatile uint16_t _rx_head = 0; /* 下一次写入位置 */
static volatile uint16_t _rx_tail = 0; /* 下一次读取位置 */

void hc05_init(void)
{
    uart_pin_init_ex(HC05_UART, HC05_UART_TX_GPIO, HC05_UART_TX_Pin,
                     HC05_UART_RX_GPIO, HC05_UART_RX_Pin);
    uart_baud_config(HC05_UART, HC05_BAUDRATE); /* 9600：HC05 出厂默认 */

    gpio_init(HC05_STATE_GPIO, HC05_STATE_PIN, IU); /* STATE 上拉输入 */
    gpio_init(HC05_KEY_GPIO, HC05_KEY_PIN, OUT_PP); /* KEY 推挽输出 */

    _rx_head = 0;
    _rx_tail = 0;

    /* KEY 默认拉低 = 透传模式（进入 AT 需重新上电并保持 KEY 高） */
    gpio_set(HC05_KEY_GPIO, HC05_KEY_PIN, 0);
}

void hc05_send_char(uint8_t ch)
{
    uart_sendbyte(HC05_UART, ch); /* ml_uart：SR.TC 忙等后写 DR */
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
    uint8_t level = gpio_get(HC05_STATE_GPIO, HC05_STATE_PIN);
    return (level == HC05_CONNECTED_LEVEL) ? 1 : 0;
}

void hc05_at_mode_enter(void)
{
    /* HC05 硬件：KEY 高电平 + 重新上电 = AT 命令模式（默认 38400）；
     * 程序内切换后必须断电重启才生效，此处仅驱动引脚电平并注释说明。 */
    gpio_set(HC05_KEY_GPIO, HC05_KEY_PIN, 1);
}

void hc05_at_mode_exit(void)
{
    gpio_set(HC05_KEY_GPIO, HC05_KEY_PIN, 0);
}

/* RX 中断处理（母版 isr.c 的 USART1_IRQHandler 经 USART1_IRQ_CALLS 聚合宏
 * 调用——pinwriter `_UART_CALLS_ROLES` 登记 HC05_UART → hc05_rx_handler；
 * 仅处理 RXNE；环形缓冲满时丢新字节（读侧不消费时的背压策略）。 */
void hc05_rx_handler(void)
{
    while (HC05_UART_INST->SR & 0x20u) { /* USART_SR.RXNE（0x20） */
        uint8_t byte = (uint8_t)(HC05_UART_INST->DR & 0xFFu);
        uint16_t next = (uint16_t)((_rx_head + 1) % HC05_RX_BUF_SIZE);
        if (next != _rx_tail) {
            _rx_buf[_rx_head] = byte;
            _rx_head = next;
        }
        /* 满缓冲：丢新字节（背压策略——读侧及时消费可避免） */
    }
}
