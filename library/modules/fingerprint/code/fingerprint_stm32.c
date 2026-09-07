/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《指纹识别传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/fingerprint-recognition-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "fingerprint_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* AS608 光学指纹识别（stm32 纯驱动，真实 UART + RX 中断状态机）：
 * 页内驱动（bsp_as608.c/h）走 USART_IRQHandler 中断缓冲（u2_recv_buff +
 * u2_recv_flag，`u2_recv_length++` 无上限越界 + IDLE 不清长度），本件改
 * **结果状态机精确收帧**：fingerprint_rx_handler（母版 isr.c 聚合调用）在
 * 帧头 0xEF 0x01 FF FF FF FF 同步后按 Len 字段（大端）收齐整帧置位——响应
 * 帧 12 字节（确认码 [9]==0 判成功）、search 16 字节（[10..11]=ID）与页面
 * FPM10A_Receive_Data(12/16) 语义一致；服务函数发送后忙等整帧（超时
 * FINGERPRINT_TIMEOUT_MS=1s，页面原值）；页内 FPM10A_* 命令数组与校验和
 * 按页面原样（指令段 = 地址/命令/参数/校验和，逐字节保留）；流程控制
 * （触摸时序/按键菜单）归生成骨架（ADR 0009），页面 key_scanf/printf/main
 * 演示全剔除。 */

/* ---------- 页面命令数组（逐字节原样，校验和 = 前面字节求和 &0xFF） ---------- */

static const uint8_t _pack_head[6] = {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF}; /* 协议包头 */
static const uint8_t _cmd_check_device[10] = {0x01, 0x00, 0x07, 0x13, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1B}; /* 口令验证 */
static const uint8_t _cmd_get_img[6] = {0x01, 0x00, 0x03, 0x01, 0x00, 0x05}; /* 获得指纹图像 */
static const uint8_t _cmd_img_to_buffer1[7] = {0x01, 0x00, 0x04, 0x02, 0x01, 0x00, 0x08}; /* 图像→Buffer1 */
static const uint8_t _cmd_img_to_buffer2[7] = {0x01, 0x00, 0x04, 0x02, 0x02, 0x00, 0x09}; /* 图像→Buffer2 */
static const uint8_t _cmd_reg_model[6] = {0x01, 0x00, 0x03, 0x05, 0x00, 0x09}; /* 合成模板 */
static const uint8_t _cmd_search[11] = {0x01, 0x00, 0x08, 0x04, 0x01, 0x00, 0x00, 0x03, 0xE7, 0x00, 0xF8}; /* 搜索 0-999 */
static const uint8_t _cmd_delete_all[6] = {0x01, 0x00, 0x03, 0x0D, 0x00, 0x11}; /* 删除全部模板 */
static uint8_t _cmd_save_finger[9] = {0x01, 0x00, 0x06, 0x06, 0x01, 0x00, 0x0B, 0x00, 0x19}; /* 保存模板（ID 动态填充） */

/* ---------- RX 中断状态机（帧头同步 → Len 大端 → 精确收齐整帧） ---------- */

static volatile uint8_t _rx[FINGERPRINT_RX_BUF_SIZE]; /* 帧缓冲 */
static volatile uint8_t _rx_head = 0;  /* 帧头同步进度（0-5；6 = 已同步） */
static volatile uint8_t _rx_count = 0; /* 已收字节数 */
static volatile uint8_t _rx_expect = 0; /* 0 = 等帧头；1 = 收帧体中；>1 = 期望总长 */
static volatile uint8_t _rx_flag = 0;  /* 1 = 整帧收齐待取 */

static uint8_t _resp[FINGERPRINT_RX_BUF_SIZE]; /* 响应帧出参缓冲（服务函数消费） */

void fingerprint_rx_handler(void)
{
    while (FINGERPRINT_UART_INST->SR & 0x20u) { /* USART_SR.RXNE（0x20） */
        uint8_t byte = (uint8_t)(FINGERPRINT_UART_INST->DR & 0xFFu);

        if (_rx_expect == 0) {
            /* 帧头同步：EF 01 FF FF FF FF */
            if (byte == _pack_head[_rx_head]) {
                _rx[_rx_head++] = byte;
                if (_rx_head == 6) {
                    _rx_count = 6;
                    _rx_expect = 1; /* 进入帧体收集（PID+Len+数据+校验） */
                }
            } else {
                _rx_head = 0;
                if (byte == _pack_head[0]) {
                    _rx[_rx_head++] = byte;
                }
            }
        } else if (_rx_count < FINGERPRINT_RX_BUF_SIZE) {
            _rx[_rx_count++] = byte;
            if (_rx_count == 9) {
                /* 帧长 = 6 帧头 + PID + Len(2, 大端) + 数据段 = 9 + Len
                 * （12 字节响应 → Len=3；search 16 字节 → Len=7） */
                uint16_t total = 9u + (uint16_t)(((uint16_t)_rx[7] << 8) | _rx[8]);
                if (total > FINGERPRINT_RX_BUF_SIZE) {
                    _rx_expect = 0; /* 超长帧（噪声/异常）：丢弃重同步 */
                    _rx_head = 0;
                } else {
                    _rx_expect = (uint8_t)total;
                }
            }
            if (_rx_expect != 0 && _rx_count == _rx_expect) {
                _rx_flag = 1; /* 整帧收齐（精确 12/16 字节由 Len 字段） */
                _rx_expect = 0;
                _rx_head = 0;
            }
        } else {
            /* 缓冲满（异常超长）：丢弃并回到帧头同步（无上限越界修正） */
            _rx_expect = 0;
            _rx_head = 0;
        }
    }
}

/* ---------- UART 原语（真实 UART，忙等发送） ---------- */

static void _tx_byte(uint8_t ch)
{
    uart_sendbyte(FINGERPRINT_UART, ch); /* ml_uart：SR.TC 忙等后写 DR */
}

static void _send_packet(const uint8_t *cmd, uint8_t len)
{
    uint8_t i;
    for (i = 0; i < 6; i++) {
        _tx_byte(_pack_head[i]); /* 发送通信协议包头 */
    }
    for (i = 0; i < len; i++) {
        _tx_byte(cmd[i]);
    }
}

/* 等待整帧收齐：超时 FINGERPRINT_TIMEOUT_MS（页面 1s）内收不齐返回失败；
 * 帧长必须精确等于期望（12/16 字节——Len 字段解析即知）。返回 0 = 成功。 */
static uint8_t _wait_response(uint8_t len)
{
    uint32_t timeout = FINGERPRINT_TIMEOUT_MS;
    uint8_t i;

    while (_rx_flag == 0) {
        if (timeout == 0) {
            return 1u;
        }
        delay_ms(1);
        timeout--;
    }
    if (_rx_count != len) {
        _rx_flag = 0;
        return 1u;
    }
    for (i = 0; i < len; i++) {
        _resp[i] = _rx[i];
    }
    _rx_flag = 0;
    return 0u;
}

/* 响应帧确认码（页面 FPM10A_RECEICE_BUFFER[9]==0 判成功） */
static uint8_t _response_ok(void)
{
    return (_resp[9] == 0) ? 0u : 1u;
}

/* ---------- 对外服务函数 ---------- */

void fingerprint_init(void)
{
    uint8_t i;

    uart_pin_init_ex(FINGERPRINT_UART, FINGERPRINT_UART_TX_GPIO,
                     FINGERPRINT_UART_TX_Pin, FINGERPRINT_UART_RX_GPIO,
                     FINGERPRINT_UART_RX_Pin);
    uart_baud_config(FINGERPRINT_UART, FINGERPRINT_BAUDRATE); /* 57600：AS608 出厂默认 */
    gpio_init(FINGERPRINT_TOUCH_GPIO, FINGERPRINT_TOUCH_PIN, IU); /* 触摸上拉输入 */

    for (i = 0; i < FINGERPRINT_RX_BUF_SIZE; i++) {
        _resp[i] = 0;
    }
    _rx_head = 0;
    _rx_count = 0;
    _rx_expect = 0;
    _rx_flag = 0;
}

uint8_t fingerprint_check_device(void)
{
    uint8_t i;
    for (i = 0; i < FINGERPRINT_RX_BUF_SIZE; i++) {
        _resp[i] = 0;
    }
    _send_packet(_cmd_check_device, 10u);
    if (_wait_response(12u) != 0) {
        return 1u;
    }
    /* 统一约定：0 = 成功（页面 Device_Check 返回 1=成功，已按库风格统一） */
    return _response_ok();
}

uint8_t fingerprint_is_touched(void)
{
    return (gpio_get(FINGERPRINT_TOUCH_GPIO, FINGERPRINT_TOUCH_PIN) == 1) ? 1u : 0u;
}

uint8_t fingerprint_get_image(void)
{
    _send_packet(_cmd_get_img, 6u);
    if (_wait_response(12u) != 0) {
        return 1u;
    }
    return _response_ok();
}

uint8_t fingerprint_img_to_buffer(uint8_t buffer_id)
{
    if (buffer_id == 1u) {
        _send_packet(_cmd_img_to_buffer1, 7u);
    } else {
        _send_packet(_cmd_img_to_buffer2, 7u);
    }
    if (_wait_response(12u) != 0) {
        return 1u;
    }
    return _response_ok();
}

uint8_t fingerprint_reg_model(void)
{
    _send_packet(_cmd_reg_model, 6u);
    if (_wait_response(12u) != 0) {
        return 1u;
    }
    return _response_ok();
}

uint16_t fingerprint_search(void)
{
    _send_packet(_cmd_search, 11u);
    if (_wait_response(16u) != 0) {
        return FINGERPRINT_NOT_FOUND;
    }
    if (_response_ok() != 0) {
        return FINGERPRINT_NOT_FOUND;
    }
    return (uint16_t)(((uint16_t)_resp[10] << 8) | _resp[11]);
}

uint8_t fingerprint_save_finger(uint16_t store_id)
{
    uint8_t i;
    uint32_t temp = 0;

    _cmd_save_finger[5] = (uint8_t)((store_id & 0xFF00u) >> 8);
    _cmd_save_finger[6] = (uint8_t)(store_id & 0x00FFu);
    for (i = 0; i < 7; i++) {
        temp += _cmd_save_finger[i]; /* 计算校验和 */
    }
    _cmd_save_finger[7] = (uint8_t)((temp & 0x00FF00u) >> 8);
    _cmd_save_finger[8] = (uint8_t)(temp & 0x0000FFu);

    _send_packet(_cmd_save_finger, 9u);
    if (_wait_response(12u) != 0) {
        return 1u;
    }
    return _response_ok();
}

uint8_t fingerprint_delete_all(void)
{
    _send_packet(_cmd_delete_all, 6u);
    if (_wait_response(12u) != 0) {
        return 1u;
    }
    return _response_ok();
}

uint8_t fingerprint_enroll(uint16_t store_id)
{
    /* 页面 FPM10A_Add_Fingerprint 固定采集序列（去菜单/printf/触摸等待）：
     * 取图 → Buffer1 →（1000ms 让手指再次贴合）→ 取图 → Buffer2 → 合成 →
     * 保存；整个流程为阻塞服务函数，交互节奏归生成骨架。 */
    if (fingerprint_get_image() != 0) {
        return 1u;
    }
    delay_ms(100); /* 页面确认成功后 100ms 稳定拍（原样保留） */
    if (fingerprint_img_to_buffer(1u) != 0) {
        return 1u;
    }
    delay_ms(1000);
    if (fingerprint_get_image() != 0) {
        return 1u;
    }
    delay_ms(200);
    if (fingerprint_img_to_buffer(2u) != 0) {
        return 1u;
    }
    if (fingerprint_reg_model() != 0) {
        return 1u;
    }
    return fingerprint_save_finger(store_id);
}
