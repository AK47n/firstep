#include "headfile.h"

void gray_init()
{
	gpio_init(GPIO_B, Pin_12, IU);   // D1
	gpio_init(GPIO_B, Pin_13, IU);   // D2
	gpio_init(GPIO_B, Pin_14, IU);   // D3
	gpio_init(GPIO_B, Pin_15, IU);   // D4
	gpio_init(GPIO_A, Pin_8, IU);    // D5
	gpio_init(GPIO_C, Pin_13, IU);   // D6
	gpio_init(GPIO_C, Pin_14, IU);   // D7
	gpio_init(GPIO_C, Pin_15, IU);   // D8
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

// track() 保留为空，兼容旧调用（现在逻辑已移到 line_error_calc + PID）
void track()
{
    // 已被 line_pid_track() 替代，保留函数体以防编译报错
}

// 检测十字交叉口：全部8个传感器均检测到黑线 → 十字路口
// 返回值：1=检测到交叉口（8个传感器全黑），0=正常
unsigned char cross_detect(void)
{
	unsigned char count = 0;
	if(D1 == 0) count++;
	if(D2 == 0) count++;
	if(D3 == 0) count++;
	if(D4 == 0) count++;
	if(D5 == 0) count++;
	if(D6 == 0) count++;
	if(D7 == 0) count++;
	if(D8 == 0) count++;

	if(count >= 8) return 1;  // 全部8个传感器为黑 → 十字路口
	else           return 0;
}

// T字路口检测：6个及以上传感器检测到黑线 → T字路口或十字路口
// T字路口仅有横向黑线，中间传感器可能看到白线，因此放宽阈值
unsigned char t_cross_detect(void)
{
	unsigned char count = 0;
	if(D1 == 0) count++;
	if(D2 == 0) count++;
	if(D3 == 0) count++;
	if(D4 == 0) count++;
	if(D5 == 0) count++;
	if(D6 == 0) count++;
	if(D7 == 0) count++;
	if(D8 == 0) count++;

	if(count >= 6) return 1;  // 6个及以上传感器为黑 → T字/十字路口
	else           return 0;
}

// 返程T字路口检测：返程时从支路接近T字路口，灰度传感器仅能看到4~5个黑线
// （近端/中端返程走十字路口可用cross_detect，远端返程须用此函数）
unsigned char ret_t_cross_detect(void)
{
	unsigned char count = 0;
	if(D1 == 0) count++;
	if(D2 == 0) count++;
	if(D3 == 0) count++;
	if(D4 == 0) count++;
	if(D5 == 0) count++;
	if(D6 == 0) count++;
	if(D7 == 0) count++;
	if(D8 == 0) count++;

	if(count >= 4) return 1;  // 4个及以上传感器为黑 → 返程T字路口
	else           return 0;
}

// 全白检测：所有灰度传感器均未检测到黑线（进入药房判定，保底条件）
unsigned char all_white_detect(void)
{
	if(D1==1 && D2==1 && D3==1 && D4==1 && D5==1 && D6==1 && D7==1 && D8==1)
		return 1;
	else
		return 0;
}

// 停车区黑白块检测：检测交替排列的黑块和白块（横条黑白块图案）
// 停车区地面贴有黑色胶带条和白色间隙，各约2~3个传感器宽度，
// 灰度传感器经过时产生≥2个独立的黑色段（如11000110/10011000/11100011等）
// 正常巡线只有1个黑色段（单条黑线），全白=0个黑色段
// 返回值：1=检测到停车区黑白块图案，0=未检测到
unsigned char parking_block_detect(void)
{
	int i;
	int d[8];
	d[0] = (D1 == 0);
	d[1] = (D2 == 0);
	d[2] = (D3 == 0);
	d[3] = (D4 == 0);
	d[4] = (D5 == 0);
	d[5] = (D6 == 0);
	d[6] = (D7 == 0);
	d[7] = (D8 == 0);

	// 统计独立黑色段（连续黑传感器的段数）
	int black_segments = 0;
	int in_black = 0;
	for (i = 0; i < 8; i++)
	{
		if (d[i] && !in_black)
		{
			black_segments++;
			in_black = 1;
		}
		else if (!d[i])
		{
			in_black = 0;
		}
	}

	// 停车区特征：≥2个独立黑色段（黑白交替图案）
	// 正常巡线单黑线=1段，全白=0段，停车区=≥2段
	return (black_segments >= 2) ? 1 : 0;
}

// 启停线检测：≥4个传感器同时为黑 → 检测到A点垂直于环路的启停线
// 启停线特征：横向黑胶带(5cm) + 纵向巡线黑线交叉 → 黑色传感器数远超正常巡线(1~2个)
// 用于第2问一圈巡线后停车检测
unsigned char start_line_detect(void)
{
	unsigned char count = 0;
	if(D1 == 0) count++;
	if(D2 == 0) count++;
	if(D3 == 0) count++;
	if(D4 == 0) count++;
	if(D5 == 0) count++;
	if(D6 == 0) count++;
	if(D7 == 0) count++;
	if(D8 == 0) count++;
	return (count >= 4) ? 1 : 0;
}

unsigned char digtal(unsigned char channel)  // 读取1-8通道灰度传感器值(返回0=黑线,1=白线)
{
	u8 value = 0;
	switch(channel) 
	{
		case 1:  
			if(gpio_get(GPIO_B, Pin_12) == 1) value = 1;
			else value = 0;  
			break;  
		case 2: 
			if(gpio_get(GPIO_B, Pin_13) == 1) value = 1;
			else value = 0;  
			break;  
		case 3: 
			if(gpio_get(GPIO_B, Pin_14) == 1) value = 1;
			else value = 0;  
			break;   
		case 4:  
			if(gpio_get(GPIO_B, Pin_15) == 1) value = 1;
			else value = 0;  
			break;   
		case 5:
			if(gpio_get(GPIO_A, Pin_8) == 1) value = 1;
			else value = 0;  
			break;
		case 6:  
			if(gpio_get(GPIO_C, Pin_13) == 1) value = 1;
			else value = 0;  
			break;  
		case 7: 
			if(gpio_get(GPIO_C, Pin_14) == 1) value = 1;
			else value = 0;  
			break;  
 		case 8: 
 			if(gpio_get(GPIO_C, Pin_15) == 1) value = 1;
 			else value = 0;  
 			break;   
	}
	return value; 
}

