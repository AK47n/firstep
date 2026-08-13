/**

	 __  _______  _    ____  _  __      __  __    ____   ___  _____ _____ 

	 \ \/ /_   _|/ \  |  _ \| |/ / 塔   \ \/ /   / ___| / _ \|  ___|_   _| 软

	  \  /  | | / _ \ | |_) | ' /  克    \  /____\___ \| | | | |_    | |   件

	  /  \  | |/ ___ \|  _ <| . \  创    /  \_____|__) | |_| |  _|   | |   生

	 /_/\_\ |_/_/   \_\_| \_\_|\_\ 新   /_/\_\   |____/ \___/|_|     |_|   态

                              

  ****************************************************************************** 

  *           

  * 版权所有： XTARK@塔克创新  版权所有，盗版必究

  * 官网网站： www.xtark.cn

  * 淘宝店铺： https://shop246676508.taobao.com  

  * 塔克媒体： www.cnblogs.com/xtark（博客）

	* 塔克微信： 微信公众号：塔克创新（获取最新资讯）

  *      

  ******************************************************************************

  * @作  者  Musk Han@XTARK

  * @版  本  V1.0

  * @日  期  2019-8-2

  * @brief   电机PWM控制函数

  *

  ******************************************************************************

  * @说  明

  *

  ******************************************************************************

  */



#include "ax_motor.h" 



/**

  * @简  述  电机PWM控制初始化	

  * @参  数  freq_khz:PWM输出频率，范围1~40,单位KHz

  * @返回值  无

  */

void AX_MOTOR_Init(uint8_t freq_khz)

{  

	GPIO_InitTypeDef GPIO_InitStructure;

	TIM_TimeBaseInitTypeDef  TIM_TimeBaseStructure;

	TIM_OCInitTypeDef  TIM_OCInitStructure;

	

	RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM2, ENABLE);	//使能定时器2时钟

 	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);  //使能GPIOA外设时钟

	

  //设置该引脚为复用输出功能,输出TIM2 CH2的PWM脉冲波形	GPIOA.1

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_1; //TIM_CH2 

	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;  //复用推挽输出

	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;

	GPIO_Init(GPIOA, &GPIO_InitStructure);//初始化PWM GPIO

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_12|GPIO_Pin_11; //电机控制端口PA12、PA15

	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;  //复用推挽输出

	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;

	GPIO_Init(GPIOA, &GPIO_InitStructure);//初始化电机 GPIO

	

 	//参数过滤

	if(freq_khz == 0)freq_khz = 1;	

	if(freq_khz > 40)freq_khz = 40;

	

  //初始化TIM3

	TIM_TimeBaseStructure.TIM_Period = 2000-1; //设置在下一个更新事件装入活动的自动重装载寄存器周期的值

	TIM_TimeBaseStructure.TIM_Prescaler =72/freq_khz-1; //设置用来作为TIMx时钟频率除数的预分频值 

	TIM_TimeBaseStructure.TIM_ClockDivision = 0; //设置时钟分割:TDTS = Tck_tim

	TIM_TimeBaseStructure.TIM_CounterMode = TIM_CounterMode_Up;  //TIM向上计数模式

	TIM_TimeBaseInit(TIM2, &TIM_TimeBaseStructure); //根据TIM_TimeBaseInitStruct中指定的参数初始化TIMx的时间基数单位

	

	//初始化TIM2 Channe2 PWM模式	 

	TIM_OCInitStructure.TIM_OCMode = TIM_OCMode_PWM1; //选择定时器模式:TIM脉冲宽度调制模式2

 	TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable; //比较输出使能

	TIM_OCInitStructure.TIM_OCPolarity = TIM_OCPolarity_High; //输出极性:TIM输出比较极性高

	TIM_OC2Init(TIM2, &TIM_OCInitStructure);  //根据T指定的参数初始化外设TIM2 OC2

	TIM_OC2PreloadConfig(TIM2, TIM_OCPreload_Enable);  //使能TIM2在CCR2上的预装载寄存器 

	TIM_Cmd(TIM2, ENABLE);  //使能TIM2

}



/**

  * @简  述 电机 PWM速度控制

  * @参  数 speed 电机转速数值，范围-2000~2000

  * @返回值 无

  */

void AX_MOTOR_SetSpeed(int16_t speed)

{

	uint16_t temp;



    if(speed > 0)

	{

		GPIO_ResetBits(GPIOA, GPIO_Pin_11);

	  GPIO_SetBits(GPIOA, GPIO_Pin_12);

		temp = speed;	

	}

	else if(speed < 0)

	{

		GPIO_ResetBits(GPIOA, GPIO_Pin_12);

	  GPIO_SetBits(GPIOA, GPIO_Pin_11);

		temp = (-speed);

	}

	else

	{

		GPIO_ResetBits(GPIOA, GPIO_Pin_12);

	  GPIO_ResetBits(GPIOA, GPIO_Pin_11);

		temp = 0;

	}

	

	if(temp>2000)

		temp = 2000;

	

	TIM_SetCompare2(TIM2,temp);

}





/******************* (C) 版权 2019 XTARK **************************************/

