/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《红外测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/Infrared-distance-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef IR_DISTANCE_H
#define IR_DISTANCE_H

/* GP2Y0A02YK0F 红外测距驱动（mspm0 纯驱动，ADR 0009）：
 * - 模拟量输出：ADC 电压 → 距离（三角测量法，物体材质/温度/时间不影响精度）；
 * - 独立通道：经 adc 模块 API 读 ADC12_0 MEM3（default PA27/A0_0——手册原脚，
 *   与 adc/us016/joystick 共享同一 ADC 实例、sequence 四通道；轮询无中断）；
 * - 换算：V = raw/4095×VREF，Distance = 60.374×V^(-1.16)（GP2Y0A02YK0F
 *   官方公式 20-150cm 段）；注意 <15cm 电压跌落非线性区（随手册警告）。 */

void ir_distance_init(void);

/* 0.0f = 异常（采样为 0：未接传感器/引脚悬空——防 pow 溢出；正常量程内
 * 不会出现合法 0 值，可作失败判据）。 */
float ir_distance_read_distance_cm(void);

#endif /* IR_DISTANCE_H */
