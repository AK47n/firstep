/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《1.8寸彩色触摸屏》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/1-8-touch-color-screen.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "tp_xpt2046_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 软 SPI 位操作宏（nrf24l01/max7219 先例；XPT2046 时钟上限 ~2.3MHz——
 * 位时序按 vendor delay_us(1/6) 节拍，走库 delay 模块不占 TIMER；
 * 电平配置 = 页面原式 GPIO_Mode_Out_PP（输出三脚）+ GPIO_Mode_IPU
 * （输入两脚——上拉）→ ml_gpio OUT_PP/IU） */
#define TP_CLK(x)  gpio_set(TP_XPT2046_CLK_GPIO, TP_XPT2046_CLK_PIN, (x))
#define TP_DIN(x)  gpio_set(TP_XPT2046_DIN_GPIO, TP_XPT2046_DIN_PIN, (x))
#define TP_CS(x)   gpio_set(TP_XPT2046_CS_GPIO, TP_XPT2046_CS_PIN, (x))
#define TP_DOUT()  gpio_get(TP_XPT2046_DOUT_GPIO, TP_XPT2046_DOUT_PIN)
#define TP_PEN()   gpio_get(TP_XPT2046_PEN_GPIO, TP_XPT2046_PEN_PIN)

/* 触摸命令（vendor CMD_RDX/RDY：0xD0/0x90——方向分支常量：X = 0xD0、
 * Y = 0x90（vendor USE_HORIZONTAL==0||1 分支原样；X/Y 交换由调用方按
 * 屏方向/校准决定——本模块按 1.8 寸厂家默认方向 1 的 X/Y 定序） */
#define XPT2046_CMD_X  0xD0u
#define XPT2046_CMD_Y  0x90u

#define XPT2046_READ_TIMES 5u /* 每次坐标读取次数（vendor READ_TIMES） */
#define XPT2046_LOST_VAL   1u /* 升序排序后丢弃头尾个数（vendor LOST_VAL） */

/* 校准态（vendor tp_dev.xfac/xoff 收敛；默认 = 方向 1 出厂预设） */
static float s_xfac = 0.034810f;
static int16_t s_xoff = -5;
static float s_yfac = 0.043057f;
static int16_t s_yoff = -7;

void xpt2046_set_calibration(float xfac, float yfac, int16_t xoff,
                             int16_t yoff)
{
    s_xfac = xfac;
    s_yfac = yfac;
    s_xoff = xoff;
    s_yoff = yoff;
}

void xpt2046_init(void)
{
    /* 五脚 GPIO 初始化（stm32 版——页面原式：CLK/DIN/CS 推挽输出 +
     * DOUT/PEN 上拉输入；CS 初始高 = 片选空闲；mspm0 版由 SysConfig 配
     * 好零初始化——本版显式复用 ml_gpio 口径批次 3/01） */
    gpio_init(TP_XPT2046_CLK_GPIO, TP_XPT2046_CLK_PIN, OUT_PP);
    gpio_init(TP_XPT2046_DIN_GPIO, TP_XPT2046_DIN_PIN, OUT_PP);
    gpio_init(TP_XPT2046_CS_GPIO, TP_XPT2046_CS_PIN, OUT_PP);
    gpio_init(TP_XPT2046_DOUT_GPIO, TP_XPT2046_DOUT_PIN, IU);
    gpio_init(TP_XPT2046_PEN_GPIO, TP_XPT2046_PEN_PIN, IU);
    TP_CS(1);

    /* 出厂预设（vendor TP_Init Adujust=1：方向 1——1.8 寸厂家默认竖屏
     * 128×160；四方向预设见头文件注释，换屏/方向自设校准） */
    s_xfac = 0.034810f;
    s_xoff = -5;
    s_yfac = 0.043057f;
    s_yoff = -7;
}

/* 向 XPT2046 写 1 字节（MSB 先；CLK 上升沿有效——vendor TP_Write_Byte） */
static void xpt2046_write_byte(uint8_t num)
{
    uint8_t count;
    for (count = 0; count < 8; count++) {
        if (num & 0x80u) {
            TP_DIN(1);
        } else {
            TP_DIN(0);
        }
        num <<= 1;
        TP_CLK(0);
        delay_us(1);
        TP_CLK(1); /* 上升沿有效 */
    }
}

/* 读 1 路 ADC 值（命令 CMD：先写命令、1 个时钟清 BUSY、16 位读高 12 位；
 * vendor TP_Read_AD：CLK 低采样——读位在 CLK 上升沿后取 DOUT，归原位保留） */
static uint16_t xpt2046_read_ad(uint8_t cmd)
{
    uint8_t count;
    uint16_t num = 0;

    TP_CLK(0);
    TP_DIN(0);
    TP_CS(0);                     /* 选中触摸 IC */
    xpt2046_write_byte(cmd);      /* 发送命令字 */
    delay_us(6);
    TP_CLK(0);
    delay_us(1);
    TP_CLK(1);                    /* 给 1 个时钟，清除 BUSY */
    delay_us(1);
    TP_CLK(0);
    for (count = 0; count < 16; count++) { /* 读出 16 位数据，高 12 位有效 */
        num <<= 1;
        TP_CLK(0);
        delay_us(1);
        TP_CLK(1);
        if (TP_DOUT()) {
            num++;
        }
    }
    num >>= 4;
    TP_CS(1);                     /* 释放片选 */
    return (uint16_t)(num & 0x0FFFu);
}

/* 单轴中值滤波读数（升序排序 + 去头尾 LOST_VAL 个取均值——vendor
 * TP_Read_XOY 归一元化） */
static uint16_t xpt2046_read_xoy(uint8_t cmd)
{
    uint16_t buf[XPT2046_READ_TIMES];
    uint16_t i, j;
    uint16_t temp;
    uint16_t sum = 0;

    for (i = 0; i < XPT2046_READ_TIMES; i++) {
        buf[i] = xpt2046_read_ad(cmd);
    }
    for (i = 0; i < XPT2046_READ_TIMES - 1; i++) { /* 升序排序 */
        for (j = (uint16_t)(i + 1); j < XPT2046_READ_TIMES; j++) {
            if (buf[i] > buf[j]) {
                temp = buf[i];
                buf[i] = buf[j];
                buf[j] = temp;
            }
        }
    }
    for (i = XPT2046_LOST_VAL; i < XPT2046_READ_TIMES - XPT2046_LOST_VAL;
         i++) {
        sum = (uint16_t)(sum + buf[i]);
    }
    temp = (uint16_t)(sum / (XPT2046_READ_TIMES - 2 * XPT2046_LOST_VAL));
    return temp;
}

void xpt2046_read_raw(uint16_t *x, uint16_t *y)
{
    if (x == 0 || y == 0) {
        return;
    }
    *x = xpt2046_read_xoy(XPT2046_CMD_X);
    *y = xpt2046_read_xoy(XPT2046_CMD_Y);
}

void xpt2046_read_xy(uint16_t *x, uint16_t *y)
{
    uint16_t xr;
    uint16_t yr;
    float fx;
    float fy;
    int16_t xi;
    int16_t yi;

    if (x == 0 || y == 0) {
        return;
    }
    xpt2046_read_raw(&xr, &yr);
    fx = s_xfac * (float)xr + (float)s_xoff; /* 屏幕坐标 = 系数×原始 + 偏移 */
    fy = s_yfac * (float)yr + (float)s_yoff;
    xi = (int16_t)fx;
    yi = (int16_t)fy;
    *x = (xi < 0) ? 0 : (uint16_t)xi;
    *y = (yi < 0) ? 0 : (uint16_t)yi;
}

uint8_t xpt2046_is_pressed(void)
{
#if XPT2046_PEN_ACTIVE_LOW
    return (TP_PEN() == 0) ? 1u : 0u;
#else
    return (TP_PEN() != 0) ? 1u : 0u;
#endif
}
