/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《DS18B20温度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ds18b20-temp-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ds18b20_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* DS18B20 1-Wire 单总线位操作原语（立创 bsp 同款时序：复位低 750us、
 * 应答/释放等待按 1us 步进超时；写位 1 = 低 2us+高 60us、写位 0 = 低 60us+
 * 高 2us；读位 = 低 2us+释放+转输入 12us 采样+50us 尾部——位槽 62-64us，
 * 落页面 60-70us 区间；常量单源在 ds18b20_stm32.h，源码不散写字面量）。
 * 数据线方向运行时切换：输出（拉低/释放总线，页面原式 GPIO_Mode_Out_PP
 * → OUT_PP）+ 输入（采样从机应答与数据位，页面 GPIO_Mode_IPU → IU——
 * 模块板自带 4.7k 上拉）。 */
#define DS18B20_DATA_OUT()  gpio_init(DS18B20_GPIO, DS18B20_PIN, OUT_PP)
#define DS18B20_DATA_IN()   gpio_init(DS18B20_GPIO, DS18B20_PIN, IU)
#define DS18B20_DATA_GET()  gpio_get(DS18B20_GPIO, DS18B20_PIN)
#define DS18B20_DATA_SET(x) gpio_set(DS18B20_GPIO, DS18B20_PIN, (x))

/* 复位/检测（页面 DS18B20_Check）：拉低 ≥480us（750us）→ 释放 15us →
 * 转输入等应答拉低（200×1us 超时）→ 等释放拉高（240×1us 超时）。 */
static uint8_t ds18b20_check(void)
{
    uint16_t timeout = DS18B20_T_RESET_TIMEOUT;

    DS18B20_DATA_OUT();
    DS18B20_DATA_SET(0);
    delay_us(DS18B20_T_RESET_LOW_US);
    DS18B20_DATA_SET(1);
    delay_us(DS18B20_T_RESET_RECOVER_US);

    DS18B20_DATA_IN();
    while (DS18B20_DATA_GET() && (timeout > 0)) { /* 等从机应答拉低 */
        delay_us(1);
        timeout--;
    }
    if (timeout == 0) {
        return 1; /* 无应答：器件未接/未上电 */
    }
    timeout = DS18B20_T_RELEASE_TIMEOUT;
    while (!DS18B20_DATA_GET() && (timeout > 0)) { /* 等从机释放总线 */
        delay_us(1);
        timeout--;
    }
    if (timeout == 0) {
        return 1; /* 释放超时：总线被异常钳制 */
    }
    return 0;
}

/* 写一个字节（页面 DS18B20_Write_Byte）：LSB 先；写位 1 = 低 2us + 高 60us、
 * 写位 0 = 低 60us + 高 2us——总槽 62us。 */
static void ds18b20_write_byte(uint8_t dat)
{
    uint8_t i;

    DS18B20_DATA_OUT();
    for (i = 0; i < 8; i++) {
        if (dat & 0x01u) { /* 写 1：短低电平 + 释放拉高 */
            DS18B20_DATA_SET(0);
            delay_us(DS18B20_T_WRITE_START_US);
            DS18B20_DATA_SET(1);
            delay_us(DS18B20_T_WRITE_HIGH_US);
        } else { /* 写 0：长低电平 + 释放拉高 */
            DS18B20_DATA_SET(0);
            delay_us(DS18B20_T_WRITE_LOW_US);
            DS18B20_DATA_SET(1);
            delay_us(DS18B20_T_WRITE_END_US);
        }
        dat >>= 1;
    }
}

/* 读一个字节（页面 DS18B20_Read_Byte）：LSB 先；每个位槽 = 主机拉低 2us →
 * 释放 → 转输入 12us 处采样 → 50us 尾部——总槽 64us。 */
static uint8_t ds18b20_read_byte(void)
{
    uint8_t i;
    uint8_t dat = 0;

    for (i = 0; i < 8; i++) {
        DS18B20_DATA_OUT();
        DS18B20_DATA_SET(0);
        delay_us(DS18B20_T_READ_START_US);
        DS18B20_DATA_SET(1); /* 释放总线，让从机接管（1 = 高 / 0 = 低） */
        DS18B20_DATA_IN();
        delay_us(DS18B20_T_READ_SAMPLE_US); /* 位槽采样点（页面 12us） */
        dat >>= 1;
        if (DS18B20_DATA_GET()) {
            dat |= 0x80u;
        }
        delay_us(DS18B20_T_READ_HOLD_US); /* 位槽尾部（合计 64us，落 60-70us） */
    }
    return dat;
}

/* 启动一次温度转换（页面 DS18B20_Start）：复位 → 0xCC（跳过 ROM，单器件）→
 * 0x44（转换）；**随后按数据手册等待 12bit 最大转换时间 750ms**（页面未等
 * ——首次读回上电默认 85℃ 或不稳定值，人工复核修正记 notes）。 */
static void ds18b20_start_convert(void)
{
    (void)ds18b20_check();
    ds18b20_write_byte(0xCCu); /* 对总线上所有（唯一）设备寻址 */
    ds18b20_write_byte(0x44u); /* 启动温度转换 */
    DS18B20_DATA_OUT();
    DS18B20_DATA_SET(1); /* 转换期间释放总线（从机占用时总线被拉低） */
    delay_ms(DS18B20_CONVERT_MS);
}

uint8_t ds18b20_init(void)
{
    uint8_t st = ds18b20_check(); /* 复位检测器件（页面 DS18B20_Init/Check 语义） */
    /* 读毕释放总线（单脚配置 + 总线释放——防总线占用，批 6 口径） */
    DS18B20_DATA_OUT();
    DS18B20_DATA_SET(1);
    return st;
}

float ds18b20_read_temp(void)
{
    uint16_t temp;
    uint8_t data_l;
    uint8_t data_h;
    float value;

    ds18b20_start_convert();                    /* 0xCC + 0x44 + 750ms 转换等待 */
    (void)ds18b20_check();                      /* 复位，准备读 */
    ds18b20_write_byte(0xCCu);                  /* 跳过 ROM */
    ds18b20_write_byte(0xBEu);                  /* 读暂存器（温度寄存器） */
    data_l = ds18b20_read_byte();               /* LSB */
    data_h = ds18b20_read_byte();               /* MSB */
    temp = (uint16_t)(((uint16_t)data_h << 8) | data_l);

    if (data_h & 0x80u) {                       /* 负温：补码换算（页面原式） */
        temp = (uint16_t)((~temp) + 1u);
        value = (float)temp * (-DS18B20_TEMP_SCALE);
    } else {
        value = (float)temp * DS18B20_TEMP_SCALE; /* 正温：0.0625 系数 */
    }

    DS18B20_DATA_OUT(); /* 读毕释放总线（空闲高） */
    DS18B20_DATA_SET(1);
    return value;
}
