/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AS32-LoRa无线通信模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/rf/as32-lora-wireless-communication-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "as32.h"
#include "ti_msp_dl_config.h" /* AS32_UART_INST
                                * （SysConfig 生成命名：<实例>_INST，
                                * fingerprint/open_mv4 先例） */

/* AS32-TTL-100 433MHz LoRa 无线数传（mspm0 纯驱动）：透传字符串收发
 * （页面 LOAR_USART_send_String/HEX 原样）+ 轮询接收（页面
 * UART_1_INST_IRQHandler 中断缓冲随轮询裁剪——open_mv4「IRQHandler 随轮询
 * 裁剪」先例：DL_UART_isRXFIFOEmpty 忙等排空）。页面全局收敛为模块静态。 */

static char as32_rx_buf[AS32_RX_BUF_MAX];
static uint16_t as32_rx_len = 0;
static uint8_t as32_rx_pending = 0; /* 有新数据待取（页面 LOAR_RX_FLAG） */

/* 排空 RX FIFO → 入缓冲（页面 IRQHandler 语义改造：<实例>_INST 轮询读；
 * 满缓冲截断丢新字节——页面 (len+1)%MAX 模运算回绕覆盖首字节，人工复核
 * 修正为 cap 截断 + '\0' 收尾，notes 记录；无帧结构——行分帧归调用方） */
static void as32_drain_rx(void)
{
    uint8_t ch;

    while (DL_UART_isRXFIFOEmpty(AS32_UART_INST) == false) {
        ch = DL_UART_receiveData(AS32_UART_INST);
        if (as32_rx_len < (uint16_t)(AS32_RX_BUF_MAX - 1u)) {
            as32_rx_buf[as32_rx_len++] = (char)ch;
            as32_rx_buf[as32_rx_len] = '\0'; /* 字符串结尾补 '\0'（页面 IRQHandler） */
            as32_rx_pending = 1;
        }
        /* 满缓冲：丢弃新字节（截断保护——保首字节不被回绕覆盖） */
    }
}

/* 逐字节发送（页面 LOAR_USART_Send_Bit：忙则等待，不忙发送） */
static void as32_send_byte(uint8_t ch)
{
    while (DL_UART_isBusy(AS32_UART_INST) == true) {
    }
    DL_UART_Main_transmitData(AS32_UART_INST, ch);
}

void as32_init(void)
{
    /* 无 NVIC 使能（轮询接收——页面 LOAR_Init 的中断使能段随轮询裁剪，
     * fingerprint/open_mv4 先例）；UART 引脚/波特率由 SYSCFG_DL_init() 配置 */
    as32_flush();
}

void as32_send_string(const char *str)
{
    /* 页面原样：地址为空或者值为空跳出 */
    while (str && *str) {
        as32_send_byte((uint8_t)*str++);
    }
}

void as32_send_hex(const uint8_t *data, uint16_t len)
{
    while (len--) {
        as32_send_byte(*data++);
    }
}

uint16_t as32_receive(uint8_t *buf, uint16_t max_len)
{
    uint16_t n = 0;
    uint16_t i;

    as32_drain_rx();

    if (as32_rx_pending == 0) {
        return 0; /* 当前没有接收到数据（页面 Anakysis_Data 0 分支语义） */
    }
    as32_rx_pending = 0;

    if ((buf != NULL) && (max_len > 0u)) {
        n = as32_rx_len;
        if (n > (max_len - 1u)) {
            n = (uint16_t)(max_len - 1u); /* 截断保护：<= max_len-1 + '\0' */
        }
        for (i = 0; i < n; i++) {
            buf[i] = (uint8_t)as32_rx_buf[i];
        }
        buf[n] = '\0';
    }

    /* 读后清缓冲（页面 Anakysis_Data「读到即清」语义——标志位清除 +
     * Clear_LOAR_RX_BUFF） */
    as32_flush();
    return n;
}

void as32_flush(void)
{
    uint16_t i;

    for (i = 0; i < AS32_RX_BUF_MAX; i++) {
        as32_rx_buf[i] = 0;
    }
    as32_rx_len = 0;
    as32_rx_pending = 0;
}
