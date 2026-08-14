#include "headfile.h"
#include "gray_track.h"
#include "pin_config.h"

void gray_init()
{
	gpio_init(GRAY_D1_PORT, GRAY_D1_PIN, IU);   // D1
	gpio_init(GRAY_D2_PORT, GRAY_D2_PIN, IU);   // D2
	gpio_init(GRAY_D3_PORT, GRAY_D3_PIN, IU);   // D3
	gpio_init(GRAY_D4_PORT, GRAY_D4_PIN, IU);   // D4
	gpio_init(GRAY_D5_PORT, GRAY_D5_PIN, IU);   // D5
	gpio_init(GRAY_D6_PORT, GRAY_D6_PIN, IU);   // D6
	gpio_init(GRAY_D7_PORT, GRAY_D7_PIN, IU);   // D7
	gpio_init(GRAY_D8_PORT, GRAY_D8_PIN, IU);   // D8
}

// ===== 边缘中点法巡线：比全传感器质心更简洁、更快、更抗噪 =====
// 原理：只取黑线的左边缘和右边缘，中点在两者之间。
// 左边缘位于"最后一个白→第一个黑"之间，右边缘位于"最后一个黑→第一个白"之间。
// 传感器索引0~7 → 位置权重 = 索引×2 - 7 → 范围 -7 ~ +7（步长2）。
// 边缘插值到半传感器精度：左边缘 = left - 0.5，右边缘 = right + 0.5
// 中心 = (left - 0.5 + right + 0.5)/2 = (left + right)/2
// 位置权重 = (left + right)/2 × 2 - 7 = left + right - 7
//
// 优势：
// 1. 只依赖边缘传感器（过渡处），中间传感器噪声不影响结果
// 2. 纯整数运算，Cortex-M3无硬件浮点也极快
// 3. 连续黑块时与质心法数学等价，无需除法
//
// 返回：正值=线偏右，负值=线偏左，0=居中
float line_error_calc(void)
{
    int d[8];
    d[0] = (D1 == 0);
    d[1] = (D2 == 0);
    d[2] = (D3 == 0);
    d[3] = (D4 == 0);
    d[4] = (D5 == 0);
    d[5] = (D6 == 0);
    d[6] = (D7 == 0);
    d[7] = (D8 == 0);

    // 找左边缘（第一个黑传感器的索引）
    int left = -1;
    int i;
    for (i = 0; i < 8; i++) {
        if (d[i]) { left = i; break; }
    }

    // 找右边缘（最后一个黑传感器的索引）
    int right = -1;
    for (i = 7; i >= 0; i--) {
        if (d[i]) { right = i; break; }
    }

    // 全丢线：返回0，保持上次方向
    if (left < 0 || right < 0)
        return 0.0f;

    // 线中心位置 = 左边缘 + 右边缘的中间 → 映射到权重 -7~+7
    // 推导：center_idx = (left-0.5 + right+0.5)/2 = (left+right)/2
    //       weight = (center_idx - 3.5) × 2 = (left+right)/2 × 2 - 7 = left+right - 7
    return (float)(left + right - 7);
}

// 全白检测：所有灰度传感器均未检测到黑线（丢线判定，巡线保持上次偏差用）
unsigned char all_white_detect(void)
{
	if(D1==1 && D2==1 && D3==1 && D4==1 && D5==1 && D6==1 && D7==1 && D8==1)
		return 1;
	else
		return 0;
}

unsigned char digtal(unsigned char channel)  // 读取1-8通道灰度传感器值(返回0=黑线,1=白线)
{
	u8 value = 0;
	switch(channel)
	{
		case 1:
			if(gpio_get(GRAY_D1_PORT, GRAY_D1_PIN) == 1) value = 1;
			else value = 0;
			break;
		case 2:
			if(gpio_get(GRAY_D2_PORT, GRAY_D2_PIN) == 1) value = 1;
			else value = 0;
			break;
		case 3:
			if(gpio_get(GRAY_D3_PORT, GRAY_D3_PIN) == 1) value = 1;
			else value = 0;
			break;
		case 4:
			if(gpio_get(GRAY_D4_PORT, GRAY_D4_PIN) == 1) value = 1;
			else value = 0;
			break;
		case 5:
			if(gpio_get(GRAY_D5_PORT, GRAY_D5_PIN) == 1) value = 1;
			else value = 0;
			break;
		case 6:
			if(gpio_get(GRAY_D6_PORT, GRAY_D6_PIN) == 1) value = 1;
			else value = 0;
			break;
		case 7:
			if(gpio_get(GRAY_D7_PORT, GRAY_D7_PIN) == 1) value = 1;
			else value = 0;
			break;
 		case 8:
 			if(gpio_get(GRAY_D8_PORT, GRAY_D8_PIN) == 1) value = 1;
 			else value = 0;
 			break;
	}
	return value;
}
