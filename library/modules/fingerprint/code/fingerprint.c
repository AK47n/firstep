#include "fingerprint.h"
#include "delay.h"
#include "ti_msp_dl_config.h"

/* AS608 光学指纹识别（mspm0 纯驱动，真实 UART 轮询）：
 * 页内驱动（bsp_as608.c/h）走 UART_1_INST + UART_1_INST_IRQHandler 中断缓冲
 * （u1_recv_flag），本件改**轮询接收**：FINGERPRINT_UART 独立实例（UART0 默认，
 * enabledInterrupts 空——无 ISR 强符号、与其它 UART 模块零冲突），
 * DL_UART_isRXFIFOEmpty 忙等 + 响应帧长度精确收齐；页内 FPM10A_* 命令数组
 * 与校验和按页面原样（指令段 = 地址/命令/参数/校验和，逐字节保留）；
 * 流程控制（触摸时序/按键菜单）归生成骨架（ADR 0009），页面
 * key_scanf/printf/main 演示全剔除。 */

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

static uint8_t _resp[FINGERPRINT_RX_BUF_SIZE]; /* 响应帧缓冲 */

/* ---------- UART 原语（真实 UART，忙等发送 / 轮询接收） ---------- */

static void _tx_byte(uint8_t ch)
{
    while (DL_UART_isBusy(FINGERPRINT_UART_INST) == true) {
        /* 忙等 TX 空闲（hc05 先例） */
    }
    DL_UART_Main_transmitData(FINGERPRINT_UART_INST, ch);
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

/* 轮询接收 len 字节响应：超时 FINGERPRINT_TIMEOUT_MS（页面 1s）内收不齐
 * 返回失败；页面「中断置位 + delay_ms(100) 稳定等待」在精确计数收齐后不再
 * 需要（真机行为差异随 notes 记录）。返回 0 = 成功。 */
static uint8_t _receive_response(uint8_t len)
{
    uint8_t count = 0;
    uint32_t timeout = FINGERPRINT_TIMEOUT_MS;

    while (count < len) {
        if (DL_UART_isRXFIFOEmpty(FINGERPRINT_UART_INST) == false) {
            _resp[count++] = DL_UART_receiveData(FINGERPRINT_UART_INST);
        } else {
            if (timeout == 0) {
                break;
            }
            delay_ms(1);
            timeout--;
        }
    }
    return (count == len) ? 0u : 1u;
}

/* 响应帧确认码（页面 FPM10A_RECEICE_BUFFER[9]==0 判成功）+ 拷贝到出参 */
static uint8_t _response_ok(void)
{
    return (_resp[9] == 0) ? 0u : 1u;
}

/* ---------- 对外服务函数 ---------- */

void fingerprint_init(void)
{
    uint8_t i;
    for (i = 0; i < FINGERPRINT_RX_BUF_SIZE; i++) {
        _resp[i] = 0;
    }
}

uint8_t fingerprint_check_device(void)
{
    uint8_t i;
    for (i = 0; i < FINGERPRINT_RX_BUF_SIZE; i++) {
        _resp[i] = 0;
    }
    _send_packet(_cmd_check_device, 10u);
    if (_receive_response(12u) != 0) {
        return 0;
    }
    return _response_ok() == 0 ? 1u : 0u;
}

uint8_t fingerprint_is_touched(void)
{
    return (DL_GPIO_readPins(FINGERPRINT_PORT, FINGERPRINT_TOUCH_PIN)
            & FINGERPRINT_TOUCH_PIN) ? 1u : 0u;
}

uint8_t fingerprint_get_image(void)
{
    _send_packet(_cmd_get_img, 6u);
    if (_receive_response(12u) != 0) {
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
    if (_receive_response(12u) != 0) {
        return 1u;
    }
    return _response_ok();
}

uint8_t fingerprint_reg_model(void)
{
    _send_packet(_cmd_reg_model, 6u);
    if (_receive_response(12u) != 0) {
        return 1u;
    }
    return _response_ok();
}

uint16_t fingerprint_search(void)
{
    _send_packet(_cmd_search, 11u);
    if (_receive_response(16u) != 0) {
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
    if (_receive_response(12u) != 0) {
        return 1u;
    }
    return _response_ok();
}

uint8_t fingerprint_delete_all(void)
{
    _send_packet(_cmd_delete_all, 6u);
    if (_receive_response(12u) != 0) {
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
