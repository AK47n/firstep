#include "dht11.h"
#include "delay.h" /* delay_us / delay_ms：单总线位时序延时 */
#include "ti_msp_dl_config.h" /* DHT11_PORT / DHT11_DATA_PIN /
                               * DHT11_DATA_IOMUX（SysConfig 生成命名
                               * <实例>_<引脚名>_IOMUX，aht10 编译矩阵实测） */

/* DHT11 单总线位操作原语（立创 bsp 同款时序：起始低电平 19ms、响应等待
 * 80us 步进、位高电平分界 28us——0 码高 27us、1 码高 74us）。
 * 数据线方向运行时切换：输出（拉低/释放总线）+ 输入（采样模块响应与数据位）。 */

#define DHT11_DATA_OUT()                                     \
    do {                                                     \
        DL_GPIO_initDigitalOutput(DHT11_DATA_IOMUX);         \
        DL_GPIO_setPins(DHT11_PORT, DHT11_DATA_PIN);         \
        DL_GPIO_enableOutput(DHT11_PORT, DHT11_DATA_PIN);    \
    } while (0)

#define DHT11_DATA_IN()                    \
    do {                                  \
        DL_GPIO_initDigitalInput(DHT11_DATA_IOMUX); \
    } while (0)

#define DHT11_DATA_GET() \
    ((DL_GPIO_readPins(DHT11_PORT, DHT11_DATA_PIN) & DHT11_DATA_PIN) ? 1 : 0)

#define DHT11_DATA_SET(level)                                  \
    do {                                                       \
        if (level) {                                           \
            DL_GPIO_setPins(DHT11_PORT, DHT11_DATA_PIN);       \
        } else {                                               \
            DL_GPIO_clearPins(DHT11_PORT, DHT11_DATA_PIN);     \
        }                                                      \
    } while (0)

#define DHT11_CHECK_TIME_US 28 /* 0/1 码位高电平时长分界（0 码 27us < 28us） */
#define DHT11_WAIT_US 80       /* 响应/位等待超时步进数（1us/步，立创 bsp 原值） */

static float s_temperature = 0.0f; /* 最近一次成功读数缓存（便捷封装用） */
static float s_humidity = 0.0f;

void dht11_init(void)
{
    /* 总线空闲 = 高电平（模块数据线空闲要求，模块板白自带 4.7k~10k 上拉） */
    DHT11_DATA_OUT();
    DHT11_DATA_SET(1);
}

uint8_t dht11_read(float *temperature_c, float *humidity_rh)
{
    uint64_t val = 0;
    uint16_t i;
    uint8_t timeout;
    uint8_t verify_num;
    float small_point;

    /* 1. 起始信号：低电平 ≥18ms（立创 bsp 用 19ms）→ 释放总线高 → 等 20us */
    DHT11_DATA_OUT();
    DHT11_DATA_SET(0);
    delay_ms(19);
    DHT11_DATA_SET(1);
    delay_us(20);

    /* 2. 响应信号：转输入，等模块拉高（83us 低应答）→ 等模块拉低（87us 准备） */
    DHT11_DATA_IN();
    timeout = DHT11_WAIT_US;
    while ((!DHT11_DATA_GET()) && (timeout > 0)) {
        delay_us(1);
        timeout--;
    }
    if (timeout == 0) {
        return 1; /* 无应答：模块未上电/接线错误 */
    }
    timeout = DHT11_WAIT_US;
    while (DHT11_DATA_GET() && (timeout > 0)) {
        delay_us(1);
        timeout--;
    }
    if (timeout == 0) {
        return 1; /* 回应超时：数据线被异常钳制 */
    }

    /* 3. 数据接收：40 位，高位先出；位 0 = 低 54us + 高 27us、
     *    位 1 = 低 54us + 高 74us——区分只看高电平时长 */
    for (i = 0; i < 40; i++) {
        timeout = DHT11_WAIT_US;
        while ((!DHT11_DATA_GET()) && (timeout > 0)) { /* 等当前位低电平过去 */
            delay_us(1);
            timeout--;
        }
        delay_us(DHT11_CHECK_TIME_US); /* 越过位 0 的高电平时长 */
        if (DHT11_DATA_GET()) {
            val = (val << 1) | 1; /* 仍高 = 位 1 */
        } else {
            val <<= 1; /* 已低 = 位 0 */
        }
        timeout = DHT11_WAIT_US;
        while (DHT11_DATA_GET() && (timeout > 0)) { /* 等高电平过去，备下一位 */
            delay_us(1);
            timeout--;
        }
    }

    /* 4. 结束信号：转输出、释放总线（空闲高） */
    DHT11_DATA_OUT();
    DHT11_DATA_SET(1);

    /* 5. 校验和 = 湿整 + 湿小 + 温整 + 温小（末 8 位）与 val 末 8 位
     *（校验字节——最后接收的 8 位，val 位 0-7）比对 */
    verify_num = (uint8_t)(((val >> 32) & 0xFF) + ((val >> 24) & 0xFF) +
                           ((val >> 16) & 0xFF) + ((val >> 8) & 0xFF));
    if ((uint8_t)(val & 0xFF) != verify_num) {
        return 1; /* 校验失败：丢弃本次数据 */
    }

    /* 6. 换算：湿度 = 整 + 小数×0.1；温度 = 整 + 小数×0.1 */
    if (humidity_rh != NULL) {
        s_humidity = (float)((val >> 32) & 0xFF);
        small_point = (float)((val >> 24) & 0xFF) * 0.1f;
        s_humidity += small_point;
        *humidity_rh = s_humidity;
    }
    if (temperature_c != NULL) {
        s_temperature = (float)((val >> 16) & 0xFF);
        small_point = (float)((val >> 8) & 0xFF) * 0.1f;
        s_temperature += small_point;
        *temperature_c = s_temperature;
    }
    return 0;
}

float dht11_read_temperature(void)
{
    return s_temperature; /* 最近一次成功读数缓存（手册 Get_* 语义） */
}

float dht11_read_humidity(void)
{
    return s_humidity;
}
