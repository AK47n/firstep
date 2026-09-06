/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《DHT11温湿度传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/dht11.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "dht11_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* DHT11 单总线位操作原语（立创 bsp 同款时序：起始低电平 19ms、响应等待
 * 80us 步进、位高电平分界 28us——0 码高 27us、1 码高 74us；页面原式
 * GPIO_Mode_Out_PP（推挽输出）+ GPIO_Mode_IPU（上拉输入）→ ml_gpio
 * OUT_PP/IU——模块板自带 4.7k~10k 上拉电阻）。
 * 数据线方向运行时切换：输出（拉低/释放总线）+ 输入（采样模块响应与数据位）。 */
#define DHT11_DATA_OUT()  gpio_init(DHT11_GPIO, DHT11_PIN, OUT_PP)
#define DHT11_DATA_IN()   gpio_init(DHT11_GPIO, DHT11_PIN, IU)
#define DHT11_DATA_GET()  gpio_get(DHT11_GPIO, DHT11_PIN)
#define DHT11_DATA_SET(x) gpio_set(DHT11_GPIO, DHT11_PIN, (x))

/* 全局温湿度缓存（页面 extern float temperature/humidity 全局泄漏收敛为
 * 模块静态——缺陷⑤；read_temperature/read_humidity 便捷封装读缓存） */
static float s_temperature = 0.0f;
static float s_humidity = 0.0f;

void dht11_init(void)
{
    /* 总线空闲 = 高电平（模块数据线空闲要求——空闲必须高电平） */
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
    delay_ms(DHT11_START_MS);
    DHT11_DATA_SET(1);
    delay_us(DHT11_RELEASE_US);

    /* 2. 响应信号：转输入，等模块拉高（80us 低应答）→ 等模块拉低（80us 准备）
     *（**页面超时只减不报——坏线仍读 40bit 垃圾；本件无应答/回应超时立即
     * 返回 1**，缺陷①修正） */
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

    /* 3. 数据接收：40 位，高位先出；位 0 = 低 54us + 高 27us（< 28us 分界）、
     *    位 1 = 低 54us + 高 74us——区分只看高电平时长；位循环超时由校验和
     *    兜底（页面原样——可接受，mspm0 同款） */
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

    /* 6. 换算：湿度 = 整 + 小数×0.1；温度 = 整 + 小数×0.1（0.1 分辨率，
     * 页面原式；同时写缓存供 read_temperature/read_humidity 读取） */
    if (humidity_rh != 0) {
        s_humidity = (float)((val >> 32) & 0xFF);
        small_point = (float)((val >> 24) & 0xFF) * 0.1f;
        s_humidity += small_point;
        *humidity_rh = s_humidity;
    }
    if (temperature_c != 0) {
        s_temperature = (float)((val >> 16) & 0xFF);
        small_point = (float)((val >> 8) & 0xFF) * 0.1f;
        s_temperature += small_point;
        *temperature_c = s_temperature;
    }
    return 0;
}

float dht11_read_temperature(void)
{
    return s_temperature; /* 最近一次成功读数缓存（手册 Get_temperature 语义） */
}

float dht11_read_humidity(void)
{
    return s_humidity;
}
