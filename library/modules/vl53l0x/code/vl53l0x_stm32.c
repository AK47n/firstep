/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《VL53L0X激光测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/vl53l0x-laser-distance-sensor.html
 * 驱动来源：立创地阔星 STM32F103C8T6 移植工程（用户网盘下载并解压）——
 *   sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/
 *   STM32F103C8T6_ProjectTemplate/bsp/VL53L0X/（立创 BSP 封装 +
 *   ST 官方 VL53L0X API 全套——B 类新 slug，仅 stm32 平台条目）
 * 本代码按模块库规范改写（去演示与调试输出、I2C 原语静态化、
 * 引脚宏参数化、不引 sys.h 位带等）；使用 / 复制 / 修改 / 传播
 * 请遵循立创版权要求与 ST BSD-3-Clause 许可：标明来源与链接。 */

#include "vl53l0x_stm32.h"
#include "vl53l0x_core.h"
#include "pin_config.h"
#include "headfile.h"

/* 页面/移植工程 bsp_VL53L0X.h 的 USE_I2C_2V8=1（2.8V IO 电平模式——使能
 * SCL/SDA 外部供电模式，DataInit 内 #ifdef 分支），照移植工程保留。 */
#ifndef USE_I2C_2V8
#define USE_I2C_2V8 1
#endif

/* 器件上电默认 I2C 地址（8bit 写 = 0x52 → 7bit 0x29；页面 L26 0X52）——
 * 移植工程 BSP vl53l0x_init 会改到 0x54（缺陷③：本件保持默认不变）。 */
#define VL53L0X_ADDR 0x52u

/* 模块静态设备/测量数据实例（页面 extern vl53l0x_dev/vl53l0x_data →
 * 收敛模块静态；页面缺陷② vl53l0x_data 无声明——本件显式静态）。 */
static VL53L0X_Dev_t vl53l0x_dev;
static VL53L0X_RangingMeasurementData_t vl53l0x_data;

/* ---- 软 I2C 位操作原语（页面/移植工程 i2c.c 原式时序：SCL 半周期 5us
 * ≈ 100kHz 级总线速度；电平配置 = **OUT_OD/IU**——页面原式 Out_PP/IPU
 * 换算（缺陷⑧：PA6/PA7 与批次 2/3/4 软 I2C 件共挂总线——推挽×开漏
 * 同总线互斥；模块板自带上拉电阻）；SDA 方向运行时切换 ---- */
#define VL53L0X_SDA_OUT() gpio_init(VL53L0X_SDA_GPIO, VL53L0X_SDA_PIN, OUT_OD)
#define VL53L0X_SDA_IN()  gpio_init(VL53L0X_SDA_GPIO, VL53L0X_SDA_PIN, IU)
#define VL53L0X_SDA_GET() gpio_get(VL53L0X_SDA_GPIO, VL53L0X_SDA_PIN)
#define VL53L0X_SDA(x)    gpio_set(VL53L0X_SDA_GPIO, VL53L0X_SDA_PIN, (x))
#define VL53L0X_SCL(x)    gpio_set(VL53L0X_SCL_GPIO, VL53L0X_SCL_PIN, (x))
#define VL53L0X_XSHUT(x)  gpio_set(VL53L0X_XSHUT_GPIO, VL53L0X_XSHUT_PIN, (x))

static void vl53l0x_iic_init(void)
{
    /* SCL/SDA 初始化（批次 3/01 回修口径：F1 复位后 GPIO 浮空输入、ODR
     * 写入无效——总线空闲电平必须显式置高；页面 i2c.c Out_PP 原式换算） */
    gpio_init(VL53L0X_SCL_GPIO, VL53L0X_SCL_PIN, OUT_OD);
    VL53L0X_SCL(1);
    gpio_init(VL53L0X_SDA_GPIO, VL53L0X_SDA_PIN, OUT_OD);
    VL53L0X_SDA(1);
}

static void vl53l0x_iic_start(void)
{
    VL53L0X_SDA_OUT();
    VL53L0X_SDA(1);
    delay_us(5);
    VL53L0X_SCL(1);
    delay_us(5);
    VL53L0X_SDA(0);
    delay_us(5);
    VL53L0X_SCL(0);
    delay_us(5);
}

static void vl53l0x_iic_stop(void)
{
    VL53L0X_SDA_OUT();
    VL53L0X_SCL(0);
    VL53L0X_SDA(0);
    VL53L0X_SCL(1);
    delay_us(5);
    VL53L0X_SDA(1);
    delay_us(5);
}

static void vl53l0x_iic_send_ack(uint8_t ack)
{
    VL53L0X_SDA_OUT();
    VL53L0X_SCL(0);
    VL53L0X_SDA(0);
    delay_us(5);
    if (!ack) {
        VL53L0X_SDA(0);
    } else {
        VL53L0X_SDA(1);
    }
    VL53L0X_SCL(1);
    delay_us(5);
    VL53L0X_SCL(0);
    VL53L0X_SDA(1);
}

/* 等待从机应答（页面 I2C_WaitAck 原式：先拉高 SCL 再采样——正确版；
 * 返回 0 = 有应答、1 = 超时无应答（页面 10 次 ×5us）；页面 `char ack`
 * 死变量已剔除（缺陷⑤）。 */
static uint8_t vl53l0x_iic_wait_ack(void)
{
    uint8_t ack_flag = 10;

    VL53L0X_SCL(0);
    VL53L0X_SDA(1);
    VL53L0X_SDA_IN();
    delay_us(5);
    VL53L0X_SCL(1);
    delay_us(5);
    while ((VL53L0X_SDA_GET() == 1) && (ack_flag)) {
        ack_flag--;
        delay_us(5);
    }
    if (ack_flag <= 0) {
        vl53l0x_iic_stop();
        return 1; /* 超时无应答 */
    }
    VL53L0X_SCL(0);
    VL53L0X_SDA_OUT();
    return 0;
}

static void vl53l0x_iic_send_byte(uint8_t dat)
{
    uint8_t i;

    VL53L0X_SDA_OUT();
    VL53L0X_SCL(0); /* 拉低时钟开始数据传输 */
    for (i = 0; i < 8; i++) {
        VL53L0X_SDA((dat & 0x80u) >> 7);
        delay_us(1);
        VL53L0X_SCL(1);
        delay_us(5);
        VL53L0X_SCL(0);
        delay_us(5);
        dat <<= 1;
    }
}

/* 读一字节；ack=1 回 ACK、0 回 NACK（页面 Read_Byte 原式）
 * 返回读到的字节。 */
static uint8_t vl53l0x_iic_read_byte(uint8_t ack)
{
    uint8_t i;
    uint8_t receive = 0;

    VL53L0X_SDA_IN(); /* SDA 设置为输入 */
    for (i = 0; i < 8; i++) {
        VL53L0X_SCL(0);
        delay_us(4);
        VL53L0X_SCL(1);
        receive <<= 1;
        if (VL53L0X_SDA_GET()) {
            receive++;
        }
        delay_us(4);
    }
    if (!ack) {
        vl53l0x_iic_send_ack(1); /* 发送 nACK */
    } else {
        vl53l0x_iic_send_ack(0); /* 发送 ACK */
    }
    return receive;
}

/* ---- 传输层：寄存器寻址读写（页面 VL_IIC_Write_nByte/Read_nByte +
 * VL53L0X_write_* 原式合并；STATUS_OK=0/STATUS_FAIL=1）---- */

static uint8_t vl53l0x_iic_write_nbyte(uint8_t addr, uint8_t reg, uint16_t len,
                                       const uint8_t *buf)
{
    VL53L0X_SDA_OUT();
    vl53l0x_iic_start();
    vl53l0x_iic_send_byte(addr); /* 写地址 */
    if (vl53l0x_iic_wait_ack()) {
        vl53l0x_iic_stop();
        return 1; /* 没应答则退出 */
    }
    vl53l0x_iic_send_byte(reg);
    vl53l0x_iic_wait_ack();
    while (len--) {
        vl53l0x_iic_send_byte(*buf++);
        vl53l0x_iic_wait_ack();
    }
    vl53l0x_iic_stop();
    return 0;
}

static uint8_t vl53l0x_iic_read_nbyte(uint8_t addr, uint8_t reg, uint16_t len,
                                      uint8_t *buf)
{
    uint16_t i;

    vl53l0x_iic_start();
    vl53l0x_iic_send_byte(addr); /* 写地址 */
    if (vl53l0x_iic_wait_ack()) {
        vl53l0x_iic_stop();
        return 1;
    }
    vl53l0x_iic_send_byte(reg);
    vl53l0x_iic_wait_ack();
    vl53l0x_iic_start();
    vl53l0x_iic_send_byte((uint8_t)(addr | 0x01)); /* 读地址 */
    vl53l0x_iic_wait_ack();
    for (i = 0; i < len; i++) {
        buf[i] = vl53l0x_iic_read_byte((uint8_t)(i == len - 1 ? 0 : 1));
    }
    vl53l0x_iic_stop();
    return 0;
}

/* 连续写/读（页面 VL53L0X_write_multi/read_multi；Buffer 大端序——
 * ST API 寄存器多字节为 MSB 在前，与页面原式一致） */
static uint8_t vl53l0x_iic_write_multi(uint8_t addr, uint8_t index,
                                       const uint8_t *pdata, uint16_t count)
{
    return vl53l0x_iic_write_nbyte(addr, index, count, pdata);
}

static uint8_t vl53l0x_iic_read_multi(uint8_t addr, uint8_t index,
                                      uint8_t *pdata, uint16_t count)
{
    return vl53l0x_iic_read_nbyte(addr, index, count, pdata);
}

static uint8_t vl53l0x_iic_write_byte(uint8_t addr, uint8_t index, uint8_t data)
{
    return vl53l0x_iic_write_multi(addr, index, &data, 1);
}

static uint8_t vl53l0x_iic_write_word(uint8_t addr, uint8_t index, uint16_t data)
{
    uint8_t buffer[2];

    /* 16 位数据拆 8 位（大端） */
    buffer[0] = (uint8_t)(data >> 8);
    buffer[1] = (uint8_t)(data & 0xffu);
    if ((index & 0x01u) == 1u) {
        /* 奇地址：串行通信不能连续写非 2 字节对齐寄存器——逐字节分写
         * （缺陷⑥修正：页面/移植工程两次写 index（低字节未写）→
         * 按 ST 原式第二字节写 index+1） */
        vl53l0x_iic_write_multi(addr, index, &buffer[0], 1);
        return vl53l0x_iic_write_multi(addr, (uint8_t)(index + 1), &buffer[1], 1);
    }
    return vl53l0x_iic_write_multi(addr, index, buffer, 2);
}

static uint8_t vl53l0x_iic_write_dword(uint8_t addr, uint8_t index, uint32_t data)
{
    uint8_t buffer[4];

    buffer[0] = (uint8_t)(data >> 24);
    buffer[1] = (uint8_t)((data & 0xff0000u) >> 16);
    buffer[2] = (uint8_t)((data & 0xff00u) >> 8);
    buffer[3] = (uint8_t)(data & 0xffu);
    return vl53l0x_iic_write_multi(addr, index, buffer, 4);
}

static uint8_t vl53l0x_iic_read_byte_reg(uint8_t addr, uint8_t index,
                                         uint8_t *pdata)
{
    return vl53l0x_iic_read_multi(addr, index, pdata, 1);
}

static uint8_t vl53l0x_iic_read_word(uint8_t addr, uint8_t index, uint16_t *pdata)
{
    uint8_t buffer[2];
    uint8_t status;

    status = vl53l0x_iic_read_multi(addr, index, buffer, 2);
    *pdata = (uint16_t)(((uint16_t)buffer[0] << 8) + (uint16_t)buffer[1]);
    return status;
}

static uint8_t vl53l0x_iic_read_dword(uint8_t addr, uint8_t index, uint32_t *pdata)
{
    uint8_t buffer[4];
    uint8_t status;

    status = vl53l0x_iic_read_multi(addr, index, buffer, 4);
    *pdata = ((uint32_t)buffer[0] << 24) + ((uint32_t)buffer[1] << 16) +
             ((uint32_t)buffer[2] << 8) + (uint32_t)buffer[3];
    return status;
}

/* ---- ST 平台层（vl53l0x_api 的平台钩子——ST 官方 API 契约函数，模块内
 * 实现与声明分离（声明在裁剪核心头）；底层走上面静态原语族）---- */

VL53L0X_Error VL53L0X_WriteMulti(VL53L0X_DEV Dev, uint8_t index,
                                 uint8_t *pdata, uint32_t count)
{
    int32_t status_int;

    if (count >= VL53L0X_MAX_I2C_XFER_SIZE) {
        return VL53L0X_ERROR_INVALID_PARAMS;
    }
    status_int = vl53l0x_iic_write_multi(Dev->I2cDevAddr, index, pdata,
                                         (uint16_t)count);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

VL53L0X_Error VL53L0X_ReadMulti(VL53L0X_DEV Dev, uint8_t index, uint8_t *pdata,
                                uint32_t count)
{
    int32_t status_int;

    if (count >= VL53L0X_MAX_I2C_XFER_SIZE) {
        return VL53L0X_ERROR_INVALID_PARAMS;
    }
    status_int = vl53l0x_iic_read_multi(Dev->I2cDevAddr, index, pdata,
                                        (uint16_t)count);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

VL53L0X_Error VL53L0X_WrByte(VL53L0X_DEV Dev, uint8_t index, uint8_t data)
{
    int32_t status_int;

    status_int = vl53l0x_iic_write_byte(Dev->I2cDevAddr, index, data);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

VL53L0X_Error VL53L0X_RdByte(VL53L0X_DEV Dev, uint8_t index, uint8_t *data)
{
    int32_t status_int;

    status_int = vl53l0x_iic_read_byte_reg(Dev->I2cDevAddr, index, data);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

VL53L0X_Error VL53L0X_WrWord(VL53L0X_DEV Dev, uint8_t index, uint16_t data)
{
    int32_t status_int;

    status_int = vl53l0x_iic_write_word(Dev->I2cDevAddr, index, data);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

VL53L0X_Error VL53L0X_RdWord(VL53L0X_DEV Dev, uint8_t index, uint16_t *data)
{
    int32_t status_int;

    status_int = vl53l0x_iic_read_word(Dev->I2cDevAddr, index, data);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

VL53L0X_Error VL53L0X_WrDWord(VL53L0X_DEV Dev, uint8_t index, uint32_t data)
{
    int32_t status_int;

    status_int = vl53l0x_iic_write_dword(Dev->I2cDevAddr, index, data);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

VL53L0X_Error VL53L0X_RdDWord(VL53L0X_DEV Dev, uint8_t index, uint32_t *data)
{
    int32_t status_int;

    status_int = vl53l0x_iic_read_dword(Dev->I2cDevAddr, index, data);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

VL53L0X_Error VL53L0X_UpdateByte(VL53L0X_DEV Dev, uint8_t index,
                                 uint8_t and_data, uint8_t or_data)
{
    int32_t status_int;
    uint8_t data;

    status_int = vl53l0x_iic_read_byte_reg(Dev->I2cDevAddr, index, &data);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    data = (uint8_t)((data & and_data) | or_data);
    status_int = vl53l0x_iic_write_byte(Dev->I2cDevAddr, index, data);
    if (status_int != 0) {
        return VL53L0X_ERROR_CONTROL_INTERFACE;
    }
    return VL53L0X_ERROR_NONE;
}

/* 底层延时函数（页面 VL53L0X_PollingDelay 原式——volatile 忙等拍；
 * STA 的 measurement_poll_for_completion 等待节奏用它；
 * VL53L0X_POLLINGDELAY_LOOPNB = 250 拍（平台文件 #define——模块内
 * 保留原值） */
#define VL53L0X_POLLINGDELAY_LOOPNB 250u
VL53L0X_Error VL53L0X_PollingDelay(VL53L0X_DEV Dev)
{
    volatile uint32_t i;

    (void)Dev;
    for (i = 0; i < VL53L0X_POLLINGDELAY_LOOPNB; i++) {
        /* Do nothing */
    }
    return VL53L0X_ERROR_NONE;
}

/* ---- BSP 模式参数表（页面 bsp_VL53L0X.c Mode_data 原式——
 * 0默认/1高精度/2长距离/3高速：signalLimit/sigmaLimit/timingBudget/
 * preRangeVcselPeriod/finalRangeVcselPeriod）---- */
typedef struct {
    FixPoint1616_t signal_limit;
    FixPoint1616_t sigma_limit;
    uint32_t timing_budget;
    uint8_t pre_range_vcsel_period;
    uint8_t final_range_vcsel_period;
} vl53l0x_mode_data_t;

static const vl53l0x_mode_data_t vl53l0x_modes[4] = {
    {(FixPoint1616_t)(0.25 * 65536), (FixPoint1616_t)(18 * 65536),
     33000u, 14u, 10u}, /* 默认 */
    {(FixPoint1616_t)(0.25 * 65536), (FixPoint1616_t)(18 * 65536),
     200000u, 14u, 10u}, /* 高精度 */
    {(FixPoint1616_t)(0.1 * 65536), (FixPoint1616_t)(60 * 65536),
     33000u, 18u, 14u}, /* 长距离 */
    {(FixPoint1616_t)(0.25 * 65536), (FixPoint1616_t)(32 * 65536),
     20000u, 14u, 10u}, /* 高速 */
};

/* vl53l0x 复位（页面 vl53l0x_reset 原式：XSHUT 关 30ms/开 30ms +
 * DataInit；地址恢复省去——本件地址恒 0x52（缺陷③）） */
static void vl53l0x_reset(void)
{
    VL53L0X_XSHUT(0); /* 失能 */
    delay_ms(30);
    VL53L0X_XSHUT(1); /* 使能（I2C 地址恢复默认 0X52） */
    delay_ms(30);
    vl53l0x_dev.I2cDevAddr = VL53L0X_ADDR;
    (void)VL53L0X_DataInit(&vl53l0x_dev);
}

uint8_t vl53l0x_init(void)
{
    /* XSHUT 复位序列（页面 vl53l0x_init 原式：GPIO 初始化 + 软 I2C
     * 初始化 + XSHUT 关 50ms/开 50ms + DataInit；去 vl53l0x_Addr_set
     * 0x54 地址重设（缺陷③）与 GetDeviceInfo ID 校验演示） */
    gpio_init(VL53L0X_XSHUT_GPIO, VL53L0X_XSHUT_PIN, OUT_PP);
    vl53l0x_dev.I2cDevAddr = VL53L0X_ADDR; /* I2C 地址（上电默认 0x52） */
    vl53l0x_dev.comms_type = 1;            /* I2C 通信模式 */
    vl53l0x_dev.comms_speed_khz = 400;     /* 页面声明 400kHz（元数据） */
    vl53l0x_iic_init();                    /* 初始化 IIC 总线 */
    VL53L0X_XSHUT(0); /* 失能 */
    delay_ms(50);
    VL53L0X_XSHUT(1); /* 使能，让传感器处于工作 */
    delay_ms(50);
    return (uint8_t)VL53L0X_DataInit(&vl53l0x_dev);
}

uint8_t vl53l0x_set_mode(uint8_t mode)
{
    VL53L0X_Error status = VL53L0X_ERROR_NONE;
    uint8_t vhv_settings = 0;
    uint8_t phase_cal = 0;
    uint32_t ref_spad_count = 0;
    uint8_t is_aperture_spads = 0;

    if (mode > VL53L0X_MODE_HIGH_SPEED) {
        return (uint8_t)VL53L0X_ERROR_INVALID_PARAMS;
    }

    /* 页面 vl53l0x_set_mode 原式：复位（频繁切换工作模式容易导致采集
     * 距离数据不准——需复位）+ StaticInit + 校准（PerformRefCalibration
     * 先、PerformRefSpadManagement 后——页面顺序）+ 单次模式/限检/预算/
     * VCSEL 写入；校准缓存路径（AjustOK/24c02）剔除（缺陷⑦） */
    vl53l0x_reset();
    status = VL53L0X_StaticInit(&vl53l0x_dev);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    status = VL53L0X_PerformRefCalibration(&vl53l0x_dev, &vhv_settings,
                                           &phase_cal);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    status = VL53L0X_PerformRefSpadManagement(&vl53l0x_dev, &ref_spad_count,
                                              &is_aperture_spads);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    status = VL53L0X_SetDeviceMode(&vl53l0x_dev,
                                   VL53L0X_DEVICEMODE_SINGLE_RANGING);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    status = VL53L0X_SetLimitCheckEnable(
        &vl53l0x_dev, VL53L0X_CHECKENABLE_SIGMA_FINAL_RANGE, 1);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    status = VL53L0X_SetLimitCheckEnable(
        &vl53l0x_dev, VL53L0X_CHECKENABLE_SIGNAL_RATE_FINAL_RANGE, 1);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    status = VL53L0X_SetLimitCheckValue(
        &vl53l0x_dev, VL53L0X_CHECKENABLE_SIGMA_FINAL_RANGE,
        vl53l0x_modes[mode].sigma_limit);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    status = VL53L0X_SetLimitCheckValue(
        &vl53l0x_dev, VL53L0X_CHECKENABLE_SIGNAL_RATE_FINAL_RANGE,
        vl53l0x_modes[mode].signal_limit);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    status = VL53L0X_SetMeasurementTimingBudgetMicroSeconds(
        &vl53l0x_dev, vl53l0x_modes[mode].timing_budget);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    status = VL53L0X_SetVcselPulsePeriod(
        &vl53l0x_dev, VL53L0X_VCSEL_PERIOD_PRE_RANGE,
        vl53l0x_modes[mode].pre_range_vcsel_period);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    delay_ms(2);
    return (uint8_t)VL53L0X_SetVcselPulsePeriod(
        &vl53l0x_dev, VL53L0X_VCSEL_PERIOD_FINAL_RANGE,
        vl53l0x_modes[mode].final_range_vcsel_period);
}

uint8_t vl53l0x_read_mm(float *dist_mm)
{
    VL53L0X_Error status = VL53L0X_ERROR_NONE;

    /* 单次测距封装（页面 main 演示 PerformSingleRangingMeasurement +
     * RangeMilliMeter——缺陷①修正：每次调用独立状态、无 Status 粘滞，
     * 永远重试测距；页面演示 500ms 节流归调用方） */
    status = VL53L0X_PerformSingleRangingMeasurement(&vl53l0x_dev,
                                                     &vl53l0x_data);
    if (status != VL53L0X_ERROR_NONE) {
        return (uint8_t)status;
    }
    if (dist_mm != 0) {
        *dist_mm = (float)vl53l0x_data.RangeMilliMeter;
    }
    return 0u;
}
