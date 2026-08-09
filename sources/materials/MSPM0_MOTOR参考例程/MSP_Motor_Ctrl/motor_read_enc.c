#include "motor_Read_enc.h"


volatile int16_t	modbus_date[8];		//存储累计编码器值
volatile uint8_t modbus_rx_frame_done;   // 编码器读取完成标志位








void Modbus_ParseFrame(uint8_t data)
{
    /* 接收状态机状态 */
    static uint8_t state = 0;
		static uint8_t  modbus_reg_num;

    /* 已接收寄存器数量索引 */
    static uint8_t data_idx = 0;

    /* 临时寄存器，用于拼接高低字节 */
    static uint16_t reg_temp = 0;

    /* 接收到的 CRC 低 / 高字节 */
    static uint8_t crc_l = 0;
    static uint8_t crc_h = 0;

    /* 原始接收数据缓存，用于 CRC 校验 */
    static uint8_t modbus_raw_buf[20];   // 原始数据

    /* 原始数据索引 */
    static uint8_t raw_idx = 0;

    /* Modbus 数据区字节数 */
    static uint8_t modbus_rx_byte_cnt = 0;

    /* 临时寄存器缓冲区 */
    static uint16_t modbus_reg_buf[8];

    /* ---------------- 保存原始数据，用于 CRC 计算 ---------------- */
    if (raw_idx < 20)
        modbus_raw_buf[raw_idx++] = data;
    else
        raw_idx = 0;    // 防止溢出，直接丢帧

    /* ---------------- Modbus 接收状态机 ---------------- */
    switch (state)
    {
        case 0:     // 接收从站地址
            if (data == 0x0A)          // 判断是否为目标从站地址
                state = 1;
            else
                raw_idx = 0;           // 地址不对，丢弃数据
            break;

        case 1:     // 接收功能码
            if (data == 0x03)          // 仅解析 0x03 读保持寄存器响应
                state = 2;
            else
            {
                state = 0;             // 功能码不匹配，复位状态机
                raw_idx = 0;
            }
            break;

        case 2:     // 接收数据字节数
            modbus_rx_byte_cnt = data;

            /* 基本合法性判断：
               - 必须是偶数（一个寄存器 2 字节）
               - 寄存器数量不能超过上限 */
            if ((modbus_rx_byte_cnt & 0x01) ||
                (modbus_rx_byte_cnt / 2 > 10))   // MODBUS_MAX_REG = 10
            {
                state = 0;
                raw_idx = 0;
                break;
            }
											
            /* 计算寄存器数量 */
            modbus_reg_num = modbus_rx_byte_cnt / 2;
            data_idx = 0;
            state = 3;
            break;
										
        case 3:     // 接收寄存器高字节
            reg_temp = ((uint16_t)data << 8);
            state = 4;
            break;

        case 4:     // 接收寄存器低字节
            reg_temp |= data;
							
            /* 保存拼接好的寄存器数据 */
            if (data_idx < 10)         // MODBUS_MAX_REG
                modbus_reg_buf[data_idx++] = reg_temp;

            /* 判断是否接收完所有数据字节 */
            if ((data_idx * 2) >= modbus_rx_byte_cnt)
                state = 5;             // 数据接收完成，准备接收 CRC
            else
                state = 3;             // 继续接收下一个寄存器
            break;

        case 5:     // 接收 CRC 低字节
            crc_l = data;
            state = 6;
            break;

        case 6:     // 接收 CRC 高字节（一帧结束）
        {
            uint16_t crc_calc;
            uint16_t crc_recv;

            crc_h = data;
            crc_recv = crc_l | ((uint16_t)crc_h << 8);

            /* CRC 计算范围：
               Addr + Func + ByteCnt + Data
               即 3 + modbus_rx_byte_cnt 字节 */
            crc_calc = CRC16(modbus_raw_buf,
                             3 + modbus_rx_byte_cnt);

            /* CRC 校验正确 */
            if (crc_calc == crc_recv)
            {
                modbus_rx_frame_done = 1;   // 一帧有效的 0x03 响应

                /* 将寄存器数据复制到最终数据区 */
                for (uint8_t i = 0; i < modbus_reg_num; i++)
                {
                    modbus_date[i] = modbus_reg_buf[i];
                }
            }

            /* 复位状态机，准备接收下一帧 */
            state = 0;
            raw_idx = 0;
            break;
        }

        default:
            state = 0;
            raw_idx = 0;
            break;
    }
}




























