#ifndef TP_XPT2046_H
#define TP_XPT2046_H

#include <stdint.h>

/* XPT2046 电阻触摸驱动（mspm0，纯驱动切片，ADR 0009）：软 SPI 位操作
 * 5 脚（CLK 输出 + DIN 输出 + DOUT 输入 + CS 输出 + PEN 输入——不占硬件
 * SPI 外设/TIMER，nrf24l01/max7219 软 SPI 先例）；XPT2046 为 12 位
 * 触摸 ADC（命令 0x90/0xD0 = X/Y 通道，8 位命令 + MODE 串行 16 位读、
 * 高 12 位有效）。
 * 配套件（批次 12 决策 A）：1.8 寸屏（ZJY180S120TTG01）触摸 = 本模块
 * 独立件——与 lcd 零耦合（用户按需单选；与 LCD 共用 SCLK/MOSI 的接线由
 * 引脚绑定自选，默认脚独立互不相撞）；校准 = 出厂预设（vendor Adujust=1
 * 语义，预设为 1.8 寸 128×160 方向 1 出厂值）+ set_calibration 自设
 * （vendor 四方向预设宏 XPT2046_CAL_* 与 TP_Adjust 校准流程不随库入库——
 * 校准交互属题逻辑/骨架，ADR 0009）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/screen--1-8-touch-color-screen.md
 * （立创 wiki 地猛星移植手册；厂家例程 C:\Users\luoji\Desktop\caiping\
 * 中景园ZJY180S120TTG01技术资料\02-1.8LCD带触摸程序源码.zip
 * STM32F103C8T6 版 HARDWARE\TOUCH\touch.c/h——厂家 51/STM32 平台代码已按
 * 库规范改写：软 SPI GPIO 位操作宏化、delay 走库 delay 模块、去 TP_Scan/
 * TP_Adjust 状态机与 printf/main 演示、函数名规范化 xpt2046_*、全局
 * tp_dev 结构收敛为模块内静态校准态）。
 * 未上板（软 SPI 时序/校准系数真机验证留后续）。 */

/* 出厂预设校准方向选择（vendor TP_Init 的 USE_HORIZONTAL 四组预设；
 * 默认 init 用方向 1——1.8 寸厂家默认 USE_HORIZONTAL=1（竖屏 128×160）；
 * 其它屏/方向经 xpt2046_set_calibration 自设）。 */
#define XPT2046_CAL_DIR0  0u
#define XPT2046_CAL_DIR1  1u
#define XPT2046_CAL_DIR2  2u
#define XPT2046_CAL_DIR3  3u

/* 触摸状态电平宏（vendor PEN 输入：低 = 按下，单点可切——实物反相改 0） */
#define XPT2046_PEN_ACTIVE_LOW 1u

/* 初始化触摸屏（软 SPI 引脚由母版 SysConfig 配好，无需 GPIO 初始化）：
 * 出厂预设校准 = 方向 1（XPT2046_CAL_DIR1 预设，1.8 寸 128×160 厂家值）。 */
void xpt2046_init(void);

/* 自设校准系数（vendor Adujust=0 手动校准语义——校准演示流程归骨架：
 * 屏幕坐标 = xfac×原始值 + xoff，yfac×原始值 + yoff）。 */
void xpt2046_set_calibration(float xfac, float yfac, int16_t xoff,
                             int16_t yoff);

/* 读取原始触摸坐标（0-4095，12 位；X/Y 各 5 次读数升序排序、去头尾 1 个
 * 取均值——vendor TP_Read_XOY 中值滤波归一；读失败（读数连续同值越界）
 * 由调用方按返回坐标范围判断）。 */
void xpt2046_read_raw(uint16_t *x, uint16_t *y);

/* 读取校准后屏幕坐标（应用当前校准系数——默认预设方向 1；
 * 分辨率映射 = 校准系数决定，换屏/方向经 set_calibration）。 */
void xpt2046_read_xy(uint16_t *x, uint16_t *y);

/* 触摸状态（PEN 输入直读：1 = 按下——电平宏 XPT2046_PEN_ACTIVE_LOW；
 * 轮询使用不注册 GPIO 中断——GROUP1 单向量被 motor 编码器独占先例）。 */
uint8_t xpt2046_is_pressed(void);

#endif /* TP_XPT2046_H */
