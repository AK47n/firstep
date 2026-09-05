#ifndef IR_DISTANCE_H
#define IR_DISTANCE_H

/* GP2Y0A02YK0F 红外测距驱动（mspm0 纯驱动，ADR 0009）：
 * - 模拟量输出：ADC 电压 → 距离（三角测量法，物体材质/温度/时间不影响精度）；
 * - 独立通道：ADC12_0 MEM3（default PA27/A0_0——手册原脚，与 us016/adc/
 *   joystick 共享同一 ADC 实例、sequence 四通道）；轮询读取无中断；
 * - 换算：V = raw/4095×VREF，Distance = 60.374×V^(-1.16)（GP2Y0A02YK0F
 *   官方公式 20-150cm 段）；注意 <15cm 电压跌落非线性区（随手册警告）。 */

void ir_distance_init(void);
/* 距离（cm）20-150cm 段；内部 10 次快速平均（手册原值）；0.0f = 采样超时。 */
float ir_distance_read_distance_cm(void);

#endif /* IR_DISTANCE_H */
